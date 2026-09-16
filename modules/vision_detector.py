"""
Vision Detector Module (Enhanced with Multi-Task Analytics & Tracking)
----------------------------------------------------------------------
Features:
1. Real-time persistent tracking (ByteTrack) with track IDs for people, animals, vehicles.
2. Virtual Restricted Zone & Loitering Detection (triggers alarms on linger > threshold).
3. Stray Animal Detection & Vehicle Classification.
4. DensityNet regression for macro-crowds.
5. Hybrid auto-switching mode.
"""

import os
import sys
import cv2
import numpy as np
import torch

crowd_density_dir = os.path.join(os.path.dirname(__file__), "crowd_density")
if crowd_density_dir not in sys.path:
    sys.path.insert(0, crowd_density_dir)

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

from behavior_analytics import RestrictedZone
from traffic_animal_analytics import TrafficAnimalAnalyzer
from pool_water_segmenter import SwimmingPoolDetector


class VisionDetector:
    def __init__(self, backend="yolo", checkpoint=None, yolo_model="yolov8n.pt",
                 conf_threshold=0.35, enable_zones=True, loiter_time=5.0,
                 zone_bbox=None, zone_preset=None, auto_pool=False, device=None):
        """
        backend: 'yolo', 'density', or 'hybrid'
        checkpoint: path to DensityNet .pt model
        yolo_model: YOLO weights name
        conf_threshold: confidence threshold
        enable_zones: enable virtual restricted zones
        loiter_time: seconds before loitering alarm triggers
        zone_bbox: [xmin, ymin, xmax, ymax] normalized coordinates [0.0 - 1.0]
        zone_preset: 'center_small', 'center_medium', 'left_half', 'right_half', 'doorway'
        auto_pool: whether to automatically scan and lock onto swimming pools
        """
        self.backend = backend.lower()
        self.conf_threshold = conf_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.enable_zones = enable_zones
        self.auto_pool_enabled = auto_pool
        self.pool_locked = False
        
        self.PERSON_CLASS_ID = 0
        self.yolo = None
        self.density_net = None

        # Analytics Modules
        self.traffic_analyzer = TrafficAnimalAnalyzer()
        self.pool_detector = SwimmingPoolDetector()

        if enable_zones:
            zone_name = "🏊 Swimming Pool Safety Zone" if auto_pool else "Restricted Zone A"
            self.zone = RestrictedZone(name=zone_name, bbox=zone_bbox, loiter_threshold_sec=loiter_time)
            if zone_preset:
                self.zone.set_preset(zone_preset)
        else:
            self.zone = None

        if self.backend in ["yolo", "hybrid"]:
            if not YOLO_AVAILABLE:
                raise ImportError("Ultralytics is required for YOLO backend. Install with: pip install ultralytics")
            print(f"[VisionDetector] Loading YOLO model: {yolo_model} on {self.device}...")
            self.yolo = YOLO(yolo_model)

        if self.backend in ["density", "hybrid"]:
            if not checkpoint or not os.path.exists(checkpoint):
                # Search default model locations
                base_dir = os.path.dirname(__file__)
                candidates = [
                    os.path.join(base_dir, "crowd_density", "models", "best_density_shanghaitech_part_b.pt"),
                    os.path.join(base_dir, "crowd_density", "models", "density_shanghaitech_part_b.pt"),
                    os.path.join(base_dir, "crowd_density", "models", "best_density_synthetic_density.pt"),
                    os.path.join(base_dir, "crowd_density", "models", "density_synthetic_density.pt"),
                ]
                for cand in candidates:
                    if os.path.exists(cand):
                        checkpoint = cand
                        break

            if checkpoint and os.path.exists(checkpoint):
                from src.model import LightDensityNet
                print(f"[VisionDetector] Loading DensityNet checkpoint: {checkpoint} on {self.device}...")
                self.density_net = LightDensityNet().to(self.device)
                self.density_net.load_state_dict(torch.load(checkpoint, map_location=self.device, weights_only=True))
                self.density_net.eval()
            else:
                if self.backend == "density":
                    raise FileNotFoundError(f"DensityNet checkpoint not found at: {checkpoint}")
                self.backend = "yolo"

        print(f"[VisionDetector] Initialized with backend: '{self.backend}' | Zones Enabled: {enable_zones}")

    def set_zone_bbox(self, bbox):
        """Dynamically update restricted zone bounds [xmin, ymin, xmax, ymax]."""
        if self.zone is not None:
            self.zone.set_bbox(bbox)

    def set_zone_preset(self, preset_name):
        """Dynamically set zone preset."""
        if self.zone is not None:
            self.zone.set_preset(preset_name)

    def get_zone_config(self):
        """Get current zone configuration."""
        if self.zone is not None:
            return self.zone.get_config()
        return {"name": "None", "bbox": [0, 0, 0, 0], "loiter_threshold_sec": 0}

    def auto_detect_pool_zone(self, frame):
        """Scans frame for swimming pool water body and locks it as the restricted safety zone."""
        found, bbox, poly = self.pool_detector.detect_pool(frame)
        if found and self.zone is not None:
            self.zone.name = "🏊 Swimming Pool Safety Zone"
            self.zone.set_bbox(bbox)
            self.pool_locked = True
            print(f"[SwimmingPoolDetector] Successfully locked onto pool boundary at: {bbox}")
            return {"status": "success", "detected": True, "bbox": bbox}
        return {"status": "no_pool_detected", "detected": False, "bbox": None}

    def detect(self, frame, draw_annotations=True):
        """
        Runs full vision inference & analytics pipeline on input frame.
        Returns:
            annotated_frame (np.ndarray): Frame with visual bounding boxes / zones / telemetry.
            people_count (float): Number of people detected / estimated.
            detections (list): Detailed list of detected bounding boxes and tracking IDs.
            stats (dict): Additional metrics (animals, vehicles, loitering alerts, etc.).
        """
        # Automatic swimming pool discovery on initial frames if enabled
        if self.auto_pool_enabled and not self.pool_locked:
            self.auto_detect_pool_zone(frame)

        if self.backend == "yolo":
            return self._detect_yolo(frame, draw_annotations)
        elif self.backend == "density":
            return self._detect_density(frame, draw_annotations)
        elif self.backend == "hybrid":
            return self._detect_hybrid(frame, draw_annotations)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    def _detect_yolo(self, frame, draw_annotations=True):
        h, w = frame.shape[:2]
        
        # Use YOLO persistent tracking for consistent IDs across frames
        results = self.yolo.track(frame, imgsz=640, conf=self.conf_threshold, persist=True,
                                  verbose=False, device=self.device)
        result = results[0]

        detections = []
        people_detections = []
        annotated_frame = frame.copy() if draw_annotations else frame

        if result.boxes is not None and len(result.boxes) > 0:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy

                track_id = int(box.id[0].item()) if (box.id is not None) else 1
                label = self.yolo.names.get(cls_id, str(cls_id))

                det = {
                    "class_id": cls_id,
                    "label": label,
                    "confidence": round(conf, 2),
                    "track_id": track_id,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)]
                }
                detections.append(det)

                if cls_id == self.PERSON_CLASS_ID:
                    people_detections.append(det)

        # 1. Process Traffic & Stray Animals
        traffic_summary, traffic_events = self.traffic_analyzer.process_detections(detections)

        # 2. Process Restricted Zones & Loitering
        loitering_ids = {}
        zone_events = []
        if self.zone is not None:
            zone_events, loitering_ids = self.zone.update(people_detections, w, h)

        # 3. Draw Annotations & Overlays
        if draw_annotations:
            # Draw Restricted Zone first (underneath boxes)
            if self.zone is not None:
                annotated_frame = self.zone.draw(annotated_frame)

            # Draw Detections
            for det in detections:
                cls_id = det["class_id"]
                track_id = det["track_id"]
                x1, y1, x2, y2 = det["bbox"]
                conf = det["confidence"]
                label = det["label"]

                is_person = (cls_id == self.PERSON_CLASS_ID)
                is_loitering = (track_id in loitering_ids) if is_person else False
                is_animal = cls_id in self.traffic_analyzer.ANIMAL_CLASSES
                is_vehicle = cls_id in self.traffic_analyzer.VEHICLE_CLASSES

                if is_loitering:
                    color = (0, 0, 240)  # Bright Red for loitering alarm
                    tag = f"⚠️ #{track_id} LOITERING ({loitering_ids[track_id]:.1f}s)"
                elif is_person:
                    color = (0, 220, 0)  # Green for regular people
                    tag = f"Person #{track_id}" if track_id else "Person"
                elif is_animal:
                    color = (255, 140, 0)  # Orange for stray animals
                    tag = f"🐾 {label} #{track_id}" if track_id else f"🐾 {label}"
                elif is_vehicle:
                    color = (255, 200, 0)  # Cyan/Yellow for vehicles
                    tag = f"🚗 {label} #{track_id}" if track_id else f"🚗 {label}"
                else:
                    color = (180, 180, 180)
                    tag = f"{label}"

                # Draw bounding box
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2 if not is_loitering else 3)
                
                # Draw label badge
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
                cv2.rectangle(annotated_frame, (x1, y1 - 20), (x1 + tw + 6, y1), color, -1)
                cv2.putText(annotated_frame, tag, (x1 + 3, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255) if is_loitering else (0, 0, 0), 1, cv2.LINE_AA)

        all_events = zone_events + traffic_events
        active_alert = "none"
        if len(loitering_ids) > 0:
            active_alert = "loitering"
        elif traffic_summary["active_animals"] > 0:
            active_alert = "stray_animal"

        stats = {
            "animals": traffic_summary["active_animals"],
            "vehicles": traffic_summary["active_vehicles"],
            "loitering_count": len(loitering_ids),
            "active_alert": active_alert,
            "events": all_events,
            "backend": "yolo"
        }

        return annotated_frame, float(len(people_detections)), detections, stats

    def _detect_density(self, frame, draw_annotations=True):
        from src.model import count_from_density_map
        h, w, _ = frame.shape
        image_size = 256
        resized = cv2.resize(frame, (image_size, image_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = torch.from_numpy(np.transpose(rgb, (2, 0, 1))).unsqueeze(0).to(self.device)

        with torch.no_grad():
            dmap = self.density_net(tensor)
            count = count_from_density_map(dmap).item()

        annotated_frame = frame.copy() if draw_annotations else frame
        if draw_annotations:
            dmap_np = dmap.squeeze().cpu().numpy()
            dmap_norm = cv2.normalize(dmap_np, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            heatmap = cv2.applyColorMap(dmap_norm, cv2.COLORMAP_JET)
            heatmap_resized = cv2.resize(heatmap, (w, h))
            annotated_frame = cv2.addWeighted(annotated_frame, 0.65, heatmap_resized, 0.35, 0)

        stats = {"animals": 0, "vehicles": 0, "active_alert": "none", "events": [], "backend": "density"}
        return annotated_frame, float(max(0.0, count)), [], stats

    def _detect_hybrid(self, frame, draw_annotations=True):
        yolo_frame, yolo_count, detections, stats = self._detect_yolo(frame, draw_annotations=draw_annotations)
        if yolo_count > 30 and self.density_net is not None:
            density_frame, density_count, _, d_stats = self._detect_density(frame, draw_annotations)
            final_count = max(yolo_count, density_count)
            stats["backend"] = "hybrid (density dominant)"
            return density_frame, final_count, detections, stats
        stats["backend"] = "hybrid (yolo dominant)"
        return yolo_frame, yolo_count, detections, stats
