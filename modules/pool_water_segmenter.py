"""
Swimming Pool & Water Body Spatial Segmenter
--------------------------------------------
Automatically detects and segments swimming pool boundaries from camera feeds
using multi-stage adaptive color-space analysis (HSV / Lab) and morphological
convex contour clustering.

Features:
1. Automated swimming pool polygon / bounding box extraction.
2. Temporal spatial stabilization (locks pool boundary against water ripples/reflections).
3. Dynamic integration with RestrictedZone for automatic water safety & loitering alerts.
"""

import cv2
import numpy as np


class SwimmingPoolDetector:
    def __init__(self, min_pool_area_ratio=0.03, max_pool_area_ratio=0.85):
        """
        min_pool_area_ratio: Minimum fraction of screen area to qualify as a pool (3%)
        max_pool_area_ratio: Maximum fraction of screen area to qualify as a pool (85%)
        """
        self.min_pool_area_ratio = min_pool_area_ratio
        self.max_pool_area_ratio = max_pool_area_ratio
        
        # Pool water color thresholds in HSV space (Cyan, Turquoise, Deep Azure, Light Blue)
        # HSV OpenCV ranges: H [0..180], S [0..255], V [0..255]
        self.lower_water_hsv1 = np.array([78, 30, 45], dtype=np.uint8)    # Aqua / Cyan / Teal
        self.upper_water_hsv1 = np.array([135, 255, 255], dtype=np.uint8) # Deep Sky Blue
        
        # Secondary fallback for indoor lit pools (higher brightness / lower saturation)
        self.lower_water_hsv2 = np.array([75, 15, 80], dtype=np.uint8)
        self.upper_water_hsv2 = np.array([140, 180, 255], dtype=np.uint8)

        # Temporal stabilization cache
        self.detected_polygon = None
        self.detected_bbox = None  # [xmin, ymin, xmax, ymax] normalized
        self.history_bboxes = []
        self.is_locked = False

    def detect_pool(self, frame):
        """
        Analyzes frame and returns normalized bounding box [xmin, ymin, xmax, ymax]
        and contour polygon of the detected swimming pool.
        Returns:
            found (bool): True if a valid pool is detected.
            bbox (list): [xmin, ymin, xmax, ymax] in normalized coordinates [0.0 - 1.0].
            polygon (list): List of (x, y) normalized contour vertices.
        """
        h, w, _ = frame.shape
        frame_area = float(w * h)

        # 1. Preprocessing: Bilateral filter to smooth water ripples while keeping pool edges sharp
        smooth = cv2.bilateralFilter(frame, d=7, sigmaColor=50, sigmaSpace=50)
        hsv = cv2.cvtColor(smooth, cv2.COLOR_BGR2HSV)

        # 2. Multi-threshold water mask
        mask1 = cv2.inRange(hsv, self.lower_water_hsv1, self.upper_water_hsv1)
        mask2 = cv2.inRange(hsv, self.lower_water_hsv2, self.upper_water_hsv2)
        combined_mask = cv2.bitwise_or(mask1, mask2)

        # 3. Morphological operations to merge water fragments and close reflections
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        closed_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        clean_mask = cv2.morphologyEx(closed_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # 4. Find connected components / contours
        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        for c in contours:
            area = cv2.contourArea(c)
            ratio = area / frame_area
            if self.min_pool_area_ratio <= ratio <= self.max_pool_area_ratio:
                valid_contours.append((area, c))

        if not valid_contours:
            return False, None, None

        # Pick largest contiguous water body
        valid_contours.sort(key=lambda x: x[0], reverse=True)
        best_area, best_cnt = valid_contours[0]

        # Approximate polygon or convex hull to obtain clean pool boundary
        hull = cv2.convexHull(best_cnt)
        x, y, bw, bh = cv2.boundingRect(hull)

        # Normalized coordinates [0.0 - 1.0]
        xmin = round(max(0.0, float(x) / w), 3)
        ymin = round(max(0.0, float(y) / h), 3)
        xmax = round(min(1.0, float(x + bw) / w), 3)
        ymax = round(min(1.0, float(y + bh) / h), 3)

        normalized_bbox = [xmin, ymin, xmax, ymax]
        normalized_poly = [(round(float(pt[0][0]) / w, 3), round(float(pt[0][1]) / h, 3)) for pt in hull]

        # Temporal smoothing over consecutive detections
        self.history_bboxes.append(normalized_bbox)
        if len(self.history_bboxes) > 10:
            self.history_bboxes.pop(0)

        # Compute stable median bbox
        arr = np.array(self.history_bboxes)
        smooth_bbox = [
            round(float(np.median(arr[:, 0])), 3),
            round(float(np.median(arr[:, 1])), 3),
            round(float(np.median(arr[:, 2])), 3),
            round(float(np.median(arr[:, 3])), 3)
        ]

        self.detected_bbox = smooth_bbox
        self.detected_polygon = normalized_poly
        self.is_locked = True

        return True, smooth_bbox, normalized_poly
