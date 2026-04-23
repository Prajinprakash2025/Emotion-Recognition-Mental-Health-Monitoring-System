import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_USE_LEGACY_KERAS'] = '1'

import cv2
import numpy as np
import threading
import time
from collections import deque, Counter

import tensorflow as tf
from django.conf import settings

from .models import EmotionLog

# The user preferred the old VGG16 model as it was working better for all emotions.
MODEL_V2_PATH = os.path.join(settings.BASE_DIR, 'ml_models', 'emotion_model_v2.h5')
MODEL_V1_PATH = os.path.join(settings.BASE_DIR, 'ml_models', 'emotion_model.h5')
# Forcing the use of the old model (MODEL_V1_PATH)
MODEL_PATH = MODEL_V1_PATH
HAAR_PATH = os.path.join(settings.BASE_DIR, 'ml_models', 'haarcascade_frontalface_default.xml')


class VideoCamera(object):
    """
    High-performance threaded camera with non-blocking AI inference.
    - Camera reads run in a background thread at full speed.
    - AI inference runs in a separate thread on a timer (every 1.5s).
    - get_frame() just grabs the latest frame instantly with zero lag.
    """

    def __init__(self, user_id=None):
        self.user_id = user_id
        self.video = None
        self._stopped = False

        # Latest frame data (shared between threads)
        self._current_frame = None
        self._lock = threading.Lock()
        self._last_gray = None  # Cache grayscale for face detection

        # AI results (shared between threads)
        self._current_label = ''
        self._current_face_box = None  # (x, y, w, h) or None
        self._ai_lock = threading.Lock()

        # Emotion smoothing buffer — larger = more stable results
        self.emotion_buffer = deque(maxlen=7)
        self.last_save_time = 0

        # Per-class bias correction weights (inverse of FER2013 class frequency)
        # FER2013: Happy~8989, Neutral~6198, Sad~6077, Angry~3995,
        #          Fear~4097, Surprise~3171, Disgust~436
        # Higher weight = boost underrepresented class
        self.class_weights = np.array([
            1.8,  # Angry
            4.0,  # Disgust  (very rare in training data)
            1.7,  # Fear
            0.7,  # Happy    (most common — penalize)
            1.6,  # Sad
            2.0,  # Surprise
            1.0,  # Neutral
        ], dtype=np.float32)

        # CLAHE for lighting normalization
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Initialize camera
        print("[CAMERA] Attempting to open camera...")
        self.video = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.video.isOpened():
            print("[ERROR] Could not open video device 0. Trying index 1...")
            self.video = cv2.VideoCapture(1, cv2.CAP_DSHOW)

        if not self.video.isOpened():
            print("[ERROR] CRITICAL: No camera found!")
        else:
            print("[OK] Camera opened successfully!")
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer = less latency

        # Face detector
        self.face_classifier = cv2.CascadeClassifier(HAAR_PATH)

        # Load AI model
        print(f"[MODEL] Loading model from: {MODEL_PATH}")
        try:
            self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

            if MODEL_PATH == MODEL_V2_PATH:
                # Build the lightweight CNN architecture manually to avoid Keras version
                # config incompatibility (batch_shape / optional keywords mismatch)
                from tensorflow.keras.models import Sequential
                from tensorflow.keras.layers import (
                    Conv2D, BatchNormalization, ReLU, MaxPooling2D,
                    Dropout, Flatten, Dense
                )
                model = Sequential([
                    Conv2D(32, (3,3), padding='same', input_shape=(48,48,3)),
                    BatchNormalization(), ReLU(),
                    Conv2D(32, (3,3), padding='same'),
                    BatchNormalization(), ReLU(),
                    MaxPooling2D(2,2), Dropout(0.25),

                    Conv2D(64, (3,3), padding='same'),
                    BatchNormalization(), ReLU(),
                    Conv2D(64, (3,3), padding='same'),
                    BatchNormalization(), ReLU(),
                    MaxPooling2D(2,2), Dropout(0.25),

                    Conv2D(128, (3,3), padding='same'),
                    BatchNormalization(), ReLU(),
                    Conv2D(128, (3,3), padding='same'),
                    BatchNormalization(), ReLU(),
                    MaxPooling2D(2,2), Dropout(0.25),

                    Flatten(),
                    Dense(256), BatchNormalization(), ReLU(), Dropout(0.5),
                    Dense(7, activation='softmax')
                ])
                model.load_weights(MODEL_PATH)
                self.classifier = model
                print("[OK] Lightweight CNN weights loaded!")
            else:
                # Old VGG16 model
                from tensorflow.keras.models import Sequential
                from tensorflow.keras.layers import Flatten, Dense, Dropout
                from tensorflow.keras.applications import VGG16
                base_model = VGG16(weights=None, include_top=False, input_shape=(48, 48, 3))
                model = Sequential()
                model.add(base_model)
                model.add(Flatten())
                model.add(Dense(128, activation='relu'))
                model.add(Dropout(0.5))
                model.add(Dense(7, activation='softmax'))
                model.load_weights(MODEL_PATH)
                self.classifier = model
                self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']
                print("[OK] VGG16 model loaded (fallback)")

            # Warm up the model
            dummy = tf.constant(np.zeros((1, 48, 48, 3), dtype=np.float32))
            self.classifier(dummy, training=False)
            print("[OK] Model warmed up!")
        except Exception as e:
            print(f"[ERROR] Error loading model: {e}")
            self.classifier = None
            self.emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

        # Start background threads
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self._ai_thread = threading.Thread(target=self._ai_loop, daemon=True)
        self._ai_thread.start()

        print("[OK] Background threads started!")



    def _capture_loop(self):
        """Background thread: reads camera frames as fast as possible."""
        while not self._stopped:
            if self.video is None or not self.video.isOpened():
                time.sleep(0.1)
                continue

            success, frame = self.video.read()
            if success:
                # Resize to standard size
                frame = cv2.resize(frame, (640, 480))
                with self._lock:
                    self._current_frame = frame
            else:
                time.sleep(0.01)

    def _ai_loop(self):
        """Background thread: runs face detection + AI inference every 0.3 seconds."""
        while not self._stopped:
            time.sleep(0.3)  # Run AI every 0.3 seconds for near-instant response

            # Grab the latest frame
            with self._lock:
                frame = self._current_frame.copy() if self._current_frame is not None else None

            if frame is None:
                continue

            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_classifier.detectMultiScale(
                    gray, scaleFactor=1.3, minNeighbors=4, minSize=(60, 60)
                )

                if len(faces) == 0:
                    with self._ai_lock:
                        self._current_face_box = None
                        self._current_label = ''
                    self.emotion_buffer.clear()
                    continue

                # Pick the largest face
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

                if self.classifier:
                    roi_gray = gray[y:y+h, x:x+w]
                    # CLAHE: normalize lighting differences vs training data
                    roi_gray = self.clahe.apply(roi_gray)
                    roi_gray = cv2.resize(roi_gray, (48, 48), interpolation=cv2.INTER_AREA)
                    # Stack grayscale to 3 channels — matches how model was trained
                    roi_3ch = np.stack([roi_gray]*3, axis=-1)
                    roi = roi_3ch.astype('float32') / 255.0
                    roi = np.expand_dims(roi, axis=0)
                    roi_tensor = tf.constant(roi)

                    raw_pred = self.classifier(roi_tensor, training=False)[0].numpy()

                    # Apply bias correction: boost underrepresented emotions
                    corrected = raw_pred * self.class_weights
                    corrected = corrected / corrected.sum()  # renormalize to sum=1

                    best_idx = int(np.argmax(corrected))
                    raw_label = self.emotion_labels[best_idx]
                    confidence = float(corrected[best_idx])

                    if confidence > 0.45:
                        self.emotion_buffer.append(raw_label)

                    if self.emotion_buffer:
                        stable_label = Counter(self.emotion_buffer).most_common(1)[0][0]

                        with self._ai_lock:
                            self._current_face_box = (x, y, w, h)
                            self._current_label = stable_label

                        # Save to database
                        current_time = time.time()
                        if current_time - self.last_save_time > 3.0:
                            try:
                                EmotionLog.objects.create(
                                    user_id=self.user_id,
                                    emotion_detected=stable_label,
                                    confidence_score=confidence
                                )
                                self.last_save_time = current_time
                                print(f"[SAVE] {stable_label} ({confidence:.0%})")
                            except Exception as db_err:
                                print(f"[ERROR] DB: {db_err}")
                    else:
                        with self._ai_lock:
                            self._current_face_box = (x, y, w, h)
                else:
                    with self._ai_lock:
                        self._current_face_box = (x, y, w, h)

            except Exception as e:
                print(f"[AI ERROR] {e}")

    def get_frame(self):
        """
        Returns the latest camera frame with AI overlay drawn on top.
        This is INSTANT - no heavy processing happens here.
        """
        with self._lock:
            frame = self._current_frame.copy() if self._current_frame is not None else None

        if frame is None:
            return self._get_placeholder_frame("No Camera Found")

        # Draw the latest AI results on top of the live frame
        with self._ai_lock:
            face_box = self._current_face_box
            label = self._current_label

        if face_box is not None:
            x, y, w, h = face_box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
            if label:
                cv2.putText(frame, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Encode to JPEG with slightly lower quality for speed
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return jpeg.tobytes()

    def release(self):
        """Explicitly release camera - call when stream stops."""
        self._stopped = True
        video = getattr(self, 'video', None)
        if video is not None and video.isOpened():
            video.release()
            self.video = None

    def __del__(self):
        self.release()

    def _get_placeholder_frame(self, text):
        """Generates a black frame with error text if camera fails."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        ret, jpeg = cv2.imencode('.jpg', img)
        return jpeg.tobytes()