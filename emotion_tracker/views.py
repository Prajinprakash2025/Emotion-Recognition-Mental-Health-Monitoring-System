import time as pytime

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import render

from .camera import VideoCamera


def landing(request):
    return render(request, 'emotion_tracker/landing.html')


def gen(camera):
    try:
        pytime.sleep(0.5)
        while True:
            frame = camera.get_frame()
            if frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
            pytime.sleep(0.033)
    finally:
        camera.release()


@login_required
def video_feed(request):
    user_id = request.user.id if request.user.is_authenticated else None
    return StreamingHttpResponse(
        gen(VideoCamera(user_id=user_id)),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
