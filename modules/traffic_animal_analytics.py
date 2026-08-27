"""
Traffic & Stray Animal Analytics Module
---------------------------------------
Categorizes objects into Stray Animals (dog, cat) and Vehicles (car, motorcycle,
bicycle, bus, truck), maintaining cumulative counts and alert conditions.
"""

class TrafficAnimalAnalyzer:
    def __init__(self):
        self.ANIMAL_CLASSES = {
            15: "Cat",
            16: "Dog",
            17: "Horse",
            18: "Sheep",
            19: "Cow"
        }
        self.VEHICLE_CLASSES = {
            1: "Bicycle",
            2: "Car",
            3: "Motorcycle",
            5: "Bus",
            7: "Truck"
        }

        # Cumulative tracking
        self.total_animals_seen = 0
        self.total_vehicles_seen = 0
        self.tracked_seen_ids = set()

    def process_detections(self, detections):
        """
        detections: List of dicts with 'class_id', 'track_id', 'label', 'confidence', 'bbox'
        Returns:
            summary (dict): Current counts and vehicle breakdowns
            events (list): Alert events (e.g. stray animal detected)
        """
        active_animals = []
        active_vehicles = []
        events = []

        vehicle_breakdown = {v: 0 for v in self.VEHICLE_CLASSES.values()}
        animal_breakdown = {a: 0 for a in self.ANIMAL_CLASSES.values()}

        for det in detections:
            cls_id = det["class_id"]
            track_id = det.get("track_id")

            if cls_id in self.ANIMAL_CLASSES:
                name = self.ANIMAL_CLASSES[cls_id]
                active_animals.append(det)
                animal_breakdown[name] = animal_breakdown.get(name, 0) + 1

                if track_id is not None and track_id not in self.tracked_seen_ids:
                    self.tracked_seen_ids.add(track_id)
                    self.total_animals_seen += 1
                    events.append({
                        "type": "STRAY_ANIMAL",
                        "animal": name,
                        "track_id": track_id,
                        "confidence": det["confidence"],
                        "message": f"🐾 Stray Animal Detected: {name} (#{track_id})"
                    })

            elif cls_id in self.VEHICLE_CLASSES:
                name = self.VEHICLE_CLASSES[cls_id]
                active_vehicles.append(det)
                vehicle_breakdown[name] = vehicle_breakdown.get(name, 0) + 1

                if track_id is not None and track_id not in self.tracked_seen_ids:
                    self.tracked_seen_ids.add(track_id)
                    self.total_vehicles_seen += 1
                    events.append({
                        "type": "VEHICLE_FLOW",
                        "vehicle": name,
                        "track_id": track_id,
                        "confidence": det["confidence"],
                        "message": f"🚗 Vehicle Logged: {name} (#{track_id})"
                    })

        summary = {
            "active_animals": len(active_animals),
            "active_vehicles": len(active_vehicles),
            "animal_breakdown": animal_breakdown,
            "vehicle_breakdown": vehicle_breakdown,
            "total_animals_seen": self.total_animals_seen,
            "total_vehicles_seen": self.total_vehicles_seen
        }
        return summary, events
