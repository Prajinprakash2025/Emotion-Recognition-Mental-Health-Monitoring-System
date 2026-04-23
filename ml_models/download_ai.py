import urllib.request
import ssl
import os

# Create the folder just in case it doesn't exist
os.makedirs('.', exist_ok=True)

# Bypass SSL errors on some computers
ssl._create_default_https_context = ssl._create_unverified_context

print("1. Downloading OpenCV Haar Cascade (Face Detection)...")
xml_url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
urllib.request.urlretrieve(xml_url, "haarcascade_frontalface_default.xml")
print("✅ Haar Cascade downloaded!")

print("2. Downloading Pre-trained Emotion Model (This might take a minute)...")
# Downloading a pre-trained FER model from HuggingFace
h5_url = "https://huggingface.co/shivamprasad1001/Emo0.1/resolve/main/Emo0.1.h5"
urllib.request.urlretrieve(h5_url, "emotion_model.h5")
print("✅ Emotion Model downloaded!")

print("🎉 All AI files are ready! You can start your Django server now.")