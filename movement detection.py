
# import the necessary packages
import argparse
import datetime
import imutils
import time as ti
import cv2
import subprocess
from datetime import datetime, time
#import picamera as cam
import cloudinary.uploader
import config
import urllib3
from picamera.array import PiRGBArray
from picamera import PiCamera
import signal



now = datetime.now()
now_time = now.time()

ti.sleep(100)

time_between_resets = 5 #mins
time_between_updates = 40. #secs



# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the video file")
ap.add_argument("-a", "--min-area", type=int, default=500,
                help="minimum area size")
args = vars(ap.parse_args())
# if the video argument is None, then we are reading from webcam
if args.get("video", None) is None:
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 32
    rawCapture = PiRGBArray(camera, size=(640, 480))
    ti.sleep(0.25)

# otherwise, we are reading from a video file
else:
    camera = cv2.VideoCapture(args["video"])
# initialize the first frame in the video stream
firstFrame = None

var_time = ti.time()
update_time = ti.time()

process = None
running = False

categories = [{'name': 'person', 'id': 1}]#label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
category_index = {1: {'name': 'person', 'id': 1}}

debug_communication = 0


class Timeout():
    """Timeout class using ALARM signal."""

    class Timeout(Exception):
        pass

    def __init__(self, sec):
        self.sec = sec

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.alarm(self.sec)

    def __exit__(self, *args):
        signal.alarm(0)  # disable alarm

    def raise_timeout(self, *args):
        raise Timeout.Timeout()

def send_to_hcp(http, url, headers, qltty):
    timestamp = int(ti.time())
    timestamp = ', "timestamp":' + str(timestamp)
    quantity = '", "messages":[{"people":' + qltty
    body = '{"mode":"async", "messageType":"' + str(
        config.message_type_id_From_device) + quantity + timestamp + '}]}'
    #print('msg ID, ', config.message_type_id_From_device)
    print(body)
    r = http.urlopen('POST', url, body=body, headers=headers)
    #print('POST', url, body, headers)
    if (debug_communication == 1):
        print("send_to_hcp():" + str(r.status))
    print(r.data)


def sendinfo(long):
    try:
        urllib3.disable_warnings()
    except:
        print(
            "urllib3.disable_warnings() failed - get a recent enough urllib3 version to avoid potential InsecureRequestWarning warnings! Can and will continue though.")

    # use with or without proxy
    if (config.proxy_url == ''):
        http = urllib3.PoolManager()
    else:
        http = urllib3.proxy_from_url(config.proxy_url)

    url = 'https://iotmms' + config.hcp_account_id + config.hcp_landscape_host + '/com.sap.iotservices.mms/v1/api/http/data/' + str(
        config.device_id)
    # print("Host   " + config.hcp_account_id + config.hcp_landscape_host)

    headers = urllib3.util.make_headers(user_agent=None)

    # use with authentication
    headers['Authorization'] = 'Bearer ' + config.oauth_credentials_for_device
    headers['Content-Type'] = 'application/json;charset=utf-8'

    send_to_hcp(http, url, headers, str(long))


# loop over the frames of the video
for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True): #while True:
    #print("-----")
    if now_time >= time(8,00) and now_time <= time(18,00):
        # grab the current frame and initialize the occupied/unoccupied
        # text
        #(grabbed, frame) = camera.read() ---------------------------------
        text = "Unoccupied"

        # if the frame could not be grabbed, then we have reached the end
        # of the video
        try:
            #camera.capture(rawCapture, format="bgr")
            #image = rawCapture.array
            image = frame.array
        except:
            print("broke")
            break

        # resize the frame, convert it to grayscale, and blur it
        frame = imutils.resize(image, width=640)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        #firstFrame = background_frame()
        if ti.time() - var_time > time_between_resets * 60:
            print(ti.time() - var_time)
            firstFrame = None
            var_time = ti.time()
            print("reset")

        # if the first frame is None, initialize it
        if firstFrame is None:
            firstFrame = gray
            rawCapture.truncate(0)
            continue

        # compute the absolute difference between the current frame and
        # first frame
        frameDelta = cv2.absdiff(firstFrame, gray)
        thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

        # dilate the thresholded image to fill in holes, then find contours
        # on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]

        # loop over the contours
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < args["min_area"]:
                rawCapture.truncate(0)
                continue

            # compute the bounding box for the contour, draw it on the frame,
            # and update the text
            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            text = "Occupied"

        # draw the text and timestamp on the frame
        #cv2.putText(frame, "Room Status: {}".format(text), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        #cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        if text == "Unoccupied":
            if ti.time() - update_time > time_between_updates:
                print("send to  0 to IOT ----------------------------------------------", ti.time() - update_time)
                sendinfo(0)
                update_time = ti.time()
            ti.sleep(time_between_updates/3)
            print("There is Nobody there")
        else:
            if ti.time() - update_time > time_between_updates:
                print("send to image to cloudinary ----------------------------------------------", ti.time() - update_time)
                update_time = ti.time()
                #camera.capture('/opt/person.png')
                #return_value, image = camera.read()
                #cv2.imwrite('/opt/person.png', image)
                cv2.imwrite('person.png', image)
                try:
                    with Timeout(3):

                    #cloudinary.uploader.upload("/opt/person.png", width="640", height="480", public_id="boiiiii", api_key="156733677359362", api_secret="gUf5tbocYS8dZvA94bps3f_ALNE", cloud_name="projecteve", version="v1507590682")
                        cloudinary.uploader.upload("person.png", width="640", height="480", public_id="boiiiii",
                                               api_key="156733677359362", api_secret="gUf5tbocYS8dZvA94bps3f_ALNE",
                                               cloud_name="projecteve", version="v1507590682")
                except Exception as e:
                    print(e)
            ti.sleep(time_between_updates/3)
            print("There is a PERSON there")

        # show the frame and record if the user presses a key
        #cv2.imshow("Security Feed", frame)
        #cv2.imshow("Thresh", thresh)
        #cv2.imshow("Frame Delta", frameDelta)

        key = cv2.waitKey(1) & 0xFF

        # if the `q` key is pressed, break from the lop
        if key == ord("q"):
            break


    else:
        #print("hey")
        #camera.release()
        ti.sleep(30 *60)
        # if the video argument is None, then we are reading from webcam
        # otherwise, we are reading from a video file
    rawCapture.truncate(0)
# cleanup the camera and close any open windows
#camera.release()
cv2.destroyAllWindows()
