"""
Behavior Analytics Module
-------------------------
Implements Virtual Restricted Zone monitoring and Loitering Detection using
persistent object tracking (ByteTrack / YOLO tracking).
"""

import time
import cv2
import numpy as np


class RestrictedZone:
    def __init__(self, name="Restricted Zone", polygon=None, bbox=None, loiter_threshold_sec=5.0):
        """
        polygon: List of (x, y) normalized [0.0 - 1.0] or pixel coords [(x1, y1), (x2, y2), ...]
        bbox: [x1, y1, x2, y2] in normalized [0.0 - 1.0] or pixel coords (used if polygon is None)
        loiter_threshold_sec: Time in seconds before triggering a loitering alarm
        """
        self.name = name
        self.polygon = polygon
        # Default cleaner center box (40% width x 60% height) instead of full 80% screen
        self.bbox = bbox if bbox is not None else [0.30, 0.20, 0.70, 0.80]
        self.loiter_threshold_sec = loiter_threshold_sec

        # State tracking: track_id -> entry_timestamp
        self.tracked_objects_entry = {}
        self.active_alerts = {}

    def set_bbox(self, bbox):
        """Update zone bounding box [xmin, ymin, xmax, ymax] dynamically."""
        if len(bbox) == 4:
            self.bbox = [float(b) for b in bbox]
            self.polygon = None  # Use bbox
            print(f"[RestrictedZone] Updated zone coordinates to: {self.bbox}")

    def set_preset(self, preset_name):
        """Set predefined zone preset."""
        presets = {
            "center_small": [0.35, 0.30, 0.65, 0.70],     # Compact center (30% width)
            "center_medium": [0.25, 0.20, 0.75, 0.80],    # Standard center (50% width)
            "left_half": [0.05, 0.10, 0.48, 0.90],        # Left hallway/entrance
            "right_half": [0.52, 0.10, 0.95, 0.90],       # Right hallway/entrance
            "doorway": [0.30, 0.45, 0.70, 0.95],          # Lower doorway/gate area
            "custom": self.bbox
        }
        if preset_name in presets:
            self.set_bbox(presets[preset_name])

    def get_config(self):
        """Returns current zone configuration."""
        return {
            "name": self.name,
            "bbox": self.bbox,
            "loiter_threshold_sec": self.loiter_threshold_sec
        }

    def _get_pixel_polygon(self, frame_w, frame_h):
        if self.polygon is not None:
            # Check if normalized
            if all(0.0 <= pt[0] <= 1.0 and 0.0 <= pt[1] <= 1.0 for pt in self.polygon):
                return np.array([(int(p[0] * frame_w), int(p[1] * frame_h)) for p in self.polygon], np.int32)
            return np.array(self.polygon, np.int32)
        elif self.bbox is not None:
            b = self.bbox
            if all(0.0 <= v <= 1.0 for v in b):
                x1, y1, x2, y2 = int(b[0] * frame_w), int(b[1] * frame_h), int(b[2] * frame_w), int(b[3] * frame_h)
            else:
                x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
            return np.array([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], np.int32)
        else:
            x1, y1 = int(frame_w * 0.30), int(frame_h * 0.20)
            x2, y2 = int(frame_w * 0.70), int(frame_h * 0.80)
            return np.array([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], np.int32)

    def is_point_inside(self, point, frame_w, frame_h):
        poly = self._get_pixel_polygon(frame_w, frame_h)
        return cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False) >= 0

    def is_person_in_zone(self, bbox, frame_w, frame_h):
        """Checks if a person is inside the zone by center, feet, or significant box overlap."""
        x1, y1, x2, y2 = bbox
        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
        center_bottom = (int((x1 + x2) / 2), int(y2))
        
        # 1. Check center of body or feet
        if self.is_point_inside(center, frame_w, frame_h) or self.is_point_inside(center_bottom, frame_w, frame_h):
            return True
        
        # 2. Check bounding box overlap with zone
        poly = self._get_pixel_polygon(frame_w, frame_h)
        zx1, zy1 = np.min(poly, axis=0)
        zx2, zy2 = np.max(poly, axis=0)
        
        ix1 = max(x1, zx1)
        iy1 = max(y1, zy1)
        ix2 = min(x2, zx2)
        iy2 = min(y2, zy2)
        
        if ix2 > ix1 and iy2 > iy1:
            intersection_area = (ix2 - ix1) * (iy2 - iy1)
            box_area = max(1, (x2 - x1) * (y2 - y1))
            if (intersection_area / box_area) > 0.25:
                return True
        return False

    def update(self, detected_people, frame_w, frame_h):
        """
        detected_people: List of dicts with keys 'track_id', 'bbox' ([x1, y1, x2, y2]), 'confidence'
        Returns:
            events (list): Triggered alert messages
            loitering_ids (dict): track_id -> elapsed_seconds
        """
        now = time.time()
        current_inside_ids = set()
        loitering_ids = {}
        events = []

        for idx, p in enumerate(detected_people):
            track_id = p.get("track_id")
            if track_id is None:
                track_id = idx + 1  # Fallback to index if tracker is initializing

            bbox = p["bbox"]
            if self.is_person_in_zone(bbox, frame_w, frame_h):
                current_inside_ids.add(track_id)
                if track_id not in self.tracked_objects_entry:
                    self.tracked_objects_entry[track_id] = now
                    events.append({
                        "type": "ZONE_ENTRY",
                        "zone": self.name,
                        "track_id": track_id,
                        "timestamp": now,
                        "message": f"Person #{track_id} entered {self.name}"
                    })

                dwell_time = now - self.tracked_objects_entry[track_id]
                if dwell_time >= self.loiter_threshold_sec:
                    loitering_ids[track_id] = dwell_time
                    if track_id not in self.active_alerts:
                        self.active_alerts[track_id] = now
                        events.append({
                            "type": "LOITERING_ALERT",
                            "zone": self.name,
                            "track_id": track_id,
                            "dwell_time": round(dwell_time, 1),
                            "timestamp": now,
                            "message": f"⚠️ Loitering Alert: Person #{track_id} in {self.name} ({dwell_time:.1f}s)"
                        })

        # Clean up departed objects
        departed = set(self.tracked_objects_entry.keys()) - current_inside_ids
        for tid in departed:
            del self.tracked_objects_entry[tid]
            if tid in self.active_alerts:
                del self.active_alerts[tid]

        return events, loitering_ids

    def draw(self, frame):
        """Draws the transparent zone overlay and border."""
        h, w = frame.shape[:2]
        poly = self._get_pixel_polygon(w, h)
        
        has_alerts = len(self.active_alerts) > 0
        zone_color = (0, 0, 220) if has_alerts else (255, 180, 0)  # Red if alert, amber if normal

        # Draw semi-transparent fill
        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly], zone_color)
        alpha = 0.20 if not has_alerts else 0.35
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # Draw boundary line
        cv2.polylines(frame, [poly], isClosed=True, color=zone_color, thickness=2, lineType=cv2.LINE_AA)

        # Label tag
        pt = poly[0]
        label = f"🔒 {self.name} (Max {int(self.loiter_threshold_sec)}s)"
        if has_alerts:
            label = f"🚨 LOITERING DETECTED ({len(self.active_alerts)})"
        
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (pt[0], pt[1] - 22), (pt[0] + tw + 8, pt[1]), zone_color, -1)
        cv2.putText(frame, label, (pt[0] + 4, pt[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255) if has_alerts else (0, 0, 0), 1, cv2.LINE_AA)
        return frame
