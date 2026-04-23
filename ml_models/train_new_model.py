"""
Train a lightweight CNN for Emotion Detection on FER2013 dataset.
This replaces the heavy VGG16 model (~500MB) with a fast, accurate CNN (~2MB).

Emotions: 0=Angry, 1=Disgust, 2=Fear, 3=Happy, 4=Sad, 5=Surprise, 6=Neutral
"""

import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks

# ============================================================
# 1. DOWNLOAD FER2013 DATASET
# ============================================================
print("=" * 60)
print("STEP 1: Downloading FER2013 Dataset...")
print("=" * 60)

X_train = None

# METHOD 1: Try kagglehub (image folder format)
try:
    import kagglehub
    print("[INFO] Downloading FER2013 from Kaggle via kagglehub...")
    dataset_path = kagglehub.dataset_download("msambare/fer2013")
    print(f"[OK] Dataset downloaded to: {dataset_path}")
    
    # This dataset has folder structure: train/angry, train/happy, etc.
    from PIL import Image
    import glob
    
    emotion_map = {'angry': 0, 'disgust': 1, 'fear': 2, 'happy': 3, 'sad': 4, 'surprise': 5, 'neutral': 6}
    
    def load_images_from_folder(base_folder):
        images = []
        labels = []
        for emotion_name, label_id in emotion_map.items():
            folder = os.path.join(base_folder, emotion_name)
            if not os.path.exists(folder):
                print(f"  [WARN] Folder not found: {folder}")
                continue
            files = glob.glob(os.path.join(folder, '*.jpg')) + glob.glob(os.path.join(folder, '*.png'))
            for f in files:
                try:
                    img = Image.open(f).convert('L').resize((48, 48))
                    images.append(np.array(img))
                    labels.append(label_id)
                except:
                    pass
            print(f"  {emotion_name}: {len(files)} images")
        return np.array(images), np.array(labels)
    
    train_folder = os.path.join(dataset_path, 'train')
    test_folder = os.path.join(dataset_path, 'test')
    
    if not os.path.exists(train_folder):
        # Sometimes kagglehub nests the folder
        for root, dirs, files in os.walk(dataset_path):
            if 'train' in dirs:
                train_folder = os.path.join(root, 'train')
                test_folder = os.path.join(root, 'test')
                break
    
    print(f"\n[INFO] Loading training images from: {train_folder}")
    X_train, y_train = load_images_from_folder(train_folder)
    print(f"[INFO] Loading test images from: {test_folder}")
    X_test, y_test = load_images_from_folder(test_folder)
    
    print(f"\n[OK] Training images: {X_train.shape[0]}")
    print(f"[OK] Test images: {X_test.shape[0]}")
    
except Exception as e:
    print(f"[WARN] kagglehub failed: {e}")

# METHOD 2: Try local CSV
if X_train is None:
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fer2013.csv')
    if os.path.exists(csv_path):
        import pandas as pd
        print(f"[INFO] Loading from local CSV: {csv_path}")
        df = pd.read_csv(csv_path)
        pixels = df['pixels'].apply(lambda x: np.array(x.split(), dtype='float32'))
        X = np.stack(pixels.values).reshape(-1, 48, 48)
        y = df['emotion'].values
        train_mask = df['Usage'] == 'Training'
        test_mask = df['Usage'] != 'Training'
        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]
        print(f"[OK] Loaded from CSV. Training: {X_train.shape[0]}, Test: {X_test.shape[0]}")

if X_train is None:
    print("\n" + "!" * 60)
    print("CANNOT DOWNLOAD DATASET.")
    print("The Kaggle download may need authentication.")
    print("Please run this command first to authenticate:")
    print("  pip install kaggle")
    print("  Then go to kaggle.com -> API -> Create Token")
    print("  Place kaggle.json in C:\\Users\\HP\\.kaggle\\")
    print("!" * 60)
    exit(1)

# ============================================================
# 2. PREPROCESS DATA
# ============================================================
print("\n" + "=" * 60)
print("STEP 2: Preprocessing Data...")
print("=" * 60)

# Normalize to 0-1
X_train = X_train.astype('float32') / 255.0
X_test = X_test.astype('float32') / 255.0

# Add channel dimension (48, 48) -> (48, 48, 1) for grayscale
X_train = np.expand_dims(X_train, -1)
X_test = np.expand_dims(X_test, -1)

# Convert to 3-channel by stacking (so the model input matches the camera's color output)
X_train = np.repeat(X_train, 3, axis=-1)  # (N, 48, 48, 3)
X_test = np.repeat(X_test, 3, axis=-1)

print(f"[OK] X_train shape: {X_train.shape}")
print(f"[OK] X_test shape: {X_test.shape}")
print(f"[OK] Classes: {np.unique(y_train)}")

# Class distribution
emotion_names = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
for i, name in enumerate(emotion_names):
    count = np.sum(y_train == i)
    print(f"     {name}: {count} samples")

# ============================================================
# 3. BUILD LIGHTWEIGHT CNN MODEL
# ============================================================
print("\n" + "=" * 60)
print("STEP 3: Building Lightweight CNN Model...")
print("=" * 60)

def build_emotion_model():
    """
    Lightweight CNN for emotion detection.
    ~2MB vs VGG16's ~500MB. 50-100x faster inference.
    """
    model = keras.Sequential([
        # Input
        layers.Input(shape=(48, 48, 3)),
        
        # Block 1
        layers.Conv2D(32, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.Conv2D(32, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(pool_size=(2, 2)),
        layers.Dropout(0.25),
        
        # Block 2
        layers.Conv2D(64, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.Conv2D(64, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(pool_size=(2, 2)),
        layers.Dropout(0.25),
        
        # Block 3
        layers.Conv2D(128, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.Conv2D(128, (3, 3), padding='same'),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(pool_size=(2, 2)),
        layers.Dropout(0.25),
        
        # Classifier
        layers.Flatten(),
        layers.Dense(256),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.Dropout(0.5),
        layers.Dense(7, activation='softmax')
    ])
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model

model = build_emotion_model()
model.summary()

total_params = model.count_params()
print(f"\n[OK] Total parameters: {total_params:,}")
print(f"[OK] Model size: ~{total_params * 4 / 1024 / 1024:.1f} MB")

# ============================================================
# 4. DATA AUGMENTATION
# ============================================================
print("\n" + "=" * 60)
print("STEP 4: Setting Up Data Augmentation...")
print("=" * 60)

datagen = tf.keras.preprocessing.image.ImageDataGenerator(
    rotation_range=15,
    width_shift_range=0.1,
    height_shift_range=0.1,
    horizontal_flip=True,
    zoom_range=0.1,
)
datagen.fit(X_train)

print("[OK] Data augmentation configured (rotation, flip, shift, zoom)")

# ============================================================
# 5. TRAIN THE MODEL
# ============================================================
print("\n" + "=" * 60)
print("STEP 5: Training Model (this will take ~15-25 minutes)...")
print("=" * 60)

SAVE_PATH = os.path.join(os.path.dirname(__file__), 'emotion_model_v2.h5')

# Callbacks
cb_list = [
    callbacks.EarlyStopping(monitor='val_accuracy', patience=8, restore_best_weights=True, verbose=1),
    callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, verbose=1, min_lr=1e-6),
    callbacks.ModelCheckpoint(SAVE_PATH, monitor='val_accuracy', save_best_only=True, verbose=1),
]

EPOCHS = 40
BATCH_SIZE = 64

history = model.fit(
    datagen.flow(X_train, y_train, batch_size=BATCH_SIZE),
    epochs=EPOCHS,
    validation_data=(X_test, y_test),
    callbacks=cb_list,
    verbose=1
)

# ============================================================
# 6. EVALUATE & SAVE
# ============================================================
print("\n" + "=" * 60)
print("STEP 6: Final Evaluation...")
print("=" * 60)

test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
print(f"\n{'=' * 40}")
print(f"  FINAL TEST ACCURACY: {test_acc:.1%}")
print(f"  FINAL TEST LOSS:     {test_loss:.4f}")
print(f"{'=' * 40}")

# Save final model
model.save(SAVE_PATH)
print(f"\n[OK] Model saved to: {SAVE_PATH}")
print(f"[OK] Model size: {os.path.getsize(SAVE_PATH) / 1024 / 1024:.1f} MB")

# Per-class accuracy
predictions = model.predict(X_test, verbose=0)
pred_labels = np.argmax(predictions, axis=1)

print("\nPer-Emotion Accuracy:")
print("-" * 35)
for i, name in enumerate(emotion_names):
    mask = y_test == i
    if mask.sum() > 0:
        acc = (pred_labels[mask] == i).mean()
        print(f"  {name:10s}: {acc:.1%} ({mask.sum()} samples)")

print(f"\n{'=' * 60}")
print("TRAINING COMPLETE!")
print(f"Model saved to: {SAVE_PATH}")
print("Now update camera.py to use 'emotion_model_v2.h5'")
print(f"{'=' * 60}")
