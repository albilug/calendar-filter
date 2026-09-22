"""Course identifiers shared by the PDF importer and calendar generators."""
COURSES = {
    'seminars': ('seminari e workshop', '🎓 Seminari'),
    'machine_learning': ('advanced topics in machine learning and neural networks', '🧠 Machine Learning'),
    'human_machine_interaction': ('human machine interaction', '🤝 Human Machine Interaction'),
    'wearable_devices': ('wearable devices', '⌚ Wearable Devices'),
    'radiomics': ('radiomics', '🩻 Radiomics'),
}


def detect_course(text):
    text = ' '.join(text.lower().split())
    return next((key for key, (keyword, _) in COURSES.items() if keyword in text), None)
