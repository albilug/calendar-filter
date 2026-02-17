import requests
import re

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

# corsi da formattare
TARGET_COURSES = {
    "data science in healthcare": {
        "title": "Data Science in Healthcare",
        "emoji": "📊"
    },
    "foundations of medical research": {
        "title": "Foundations of Medical Research",
        "emoji": "🔬"
    },
    "medical informatics": {
        "title": "Medical Informatics",
        "emoji": "💻"
    },
    "diseases classification": {
        "title": "Diseases Classification and Mechanisms",
        "emoji": "🦠"
    }
}

response = requests.get(URL)
lines = response.text.splitlines()

filtered_lines = []
event_block = []
inside_event = False

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside_event = True
        event_block = []

    if inside_event:
        event_block.append(line)
    else:
        filtered_lines.append(line)

    if line.startswith("END:VEVENT"):
        inside_event = False

        summary = ""
        description = ""

        for l in event_block:
            if l.startswith("SUMMARY:"):
                summary = l.replace("SUMMARY:", "").strip()
            if l.startswith("DESCRIPTION:"):
                description = l.replace("DESCRIPTION:", "").strip()

        course_key = None
        desc_lower = description.lower()

        if "medical informatics" in desc_lower:
            course_key = "medical informatics"

        elif "foundations" in desc_lower:
            course_key = "foundations of medical research"

        elif "data science" in desc_lower:
            course_key = "data science in healthcare"

        elif "diseases classification" in desc_lower:
            course_key = "diseases classification"

        if course_key:
            course_info = TARGET_COURSES[course_key]

            # trova docente tra parentesi
            teacher = ""
            match = re.search(r"\((.*?)\)", description)
            if match:
                teacher = match.group(1)

            new_title = f"{course_info['emoji']} {course_info['title']}"

            new_description = f"Aula: {summary}"
            if teacher:
                new_description += f"\\nDocente: {teacher}"

            new_block = []
            for l in event_block:
                if l.startswith("SUMMARY:"):
                    new_block.append("SUMMARY:" + new_title)
                elif l.startswith("DESCRIPTION:"):
                    new_block.append("DESCRIPTION:" + new_description)
                else:
                    new_block.append(l)

            filtered_lines.extend(new_block)
        else:
            filtered_lines.extend(event_block)

with open("shared_calendar.ics", "w") as f:
    f.write("\n".join(filtered_lines))

print("Calendario condivisibile aggiornato!")
