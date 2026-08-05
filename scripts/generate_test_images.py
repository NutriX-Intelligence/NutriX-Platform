import cv2
import numpy as np

print("Generating test images...")

# Image 2: A clear object but not in the standard dataset (A red circle)
weird_object = np.zeros((640, 640, 3), np.uint8)
weird_object[:] = (200, 200, 200) # grey background
cv2.circle(weird_object, (320, 320), 100, (0, 0, 255), -1) # Red circle
cv2.imwrite("test_scenario_2_unknown.jpg", weird_object)
print("2. Generated test_scenario_2_unknown.jpg (A red circle)")

# Image 3: A blank white image (YOLO will find absolutely no bounding boxes here)
blank_image = np.zeros((640, 640, 3), np.uint8)
blank_image[:] = (255, 255, 255)
cv2.imwrite("test_scenario_3_blank.jpg", blank_image)
print("3. Generated test_scenario_3_blank.jpg (Blank image)")

print("Done! You can now run these through the pipeline.")
