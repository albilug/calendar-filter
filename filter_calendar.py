import requests
import re

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

FILTER_TEXT = "Diseases classification and mechanisms"

COURSES = {
    "data science in healthcare": ("📊", "Data Science"),
    "foundations of medical research": ("🔬", "Foundations"),
    "medical informatics": ("💻", "Med Info"),
    "diseases classification and mechanisms": ("🦠", "Diseases"),
}

response = requests.get(URL)
lines = response.text.splitlines()

output = []
event = []
inside = False
skip = False

def detect_course(text):
    text = text.lower()
    for key in COURSES:
        if key in text:
            return key
    return None

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside = True
        event = []
        skip = False
        course_key = None
        room = ""
        professor = ""

    if inside:
        event.append(line)

        if line.startswith("DESCRIPTION:"):
            desc = line.replace("DESCRIPTION:", "")

            course_key = detect_course(desc)

            if FILTER_TEXT.lower() in desc.lower():
                skip = True

            room_match = re.search(r"Aula\s+[A-Za-z0-9\. ]+", desc)
            if room_match:
                room = room_match.group(0)

            prof_match = re.search(r"\((.*?)\)", desc)
            if prof_match:
                professor = prof_match.group(1)

        if line.startswith("SUMMARY:") and course_key:
            emoji, short = COURSES[course_key]
            event[-1] = f"SUMMARY:{emoji} {short}"

        if line.startswith("DESCRIPTION:") and course_key:
            new_desc = " — ".join(filter(None, [room, professor]))
            event[-1] = f"DESCRIPTION:{new_desc}"

        if line.startswith("END:VEVENT"):
            inside = False
            if not skip:
                output.extend(event)

    else:
        output.append(line)

with open("filtered_calendar.ics", "w") as f:
    f.write("\n".join(output))

print("Calendario corretto e titoli abbreviati!")
