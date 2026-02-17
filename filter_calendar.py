import requests
import re

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

# corso da escludere dal calendario personale
FILTER_TEXT = "Diseases classification and mechanisms"

# corsi da abbreviare
TARGET_COURSES = {
    "data science in healthcare": {
        "title": "Data Science",
        "emoji": "📊"
    },
    "foundations of medical research": {
        "title": "Foundations",
        "emoji": "🔬"
    },
    "medical informatics": {
        "title": "Med Info",
        "emoji": "💻"
    },
    "diseases classification and mechanisms": {
        "title": "Diseases",
        "emoji": "🦠"
    }
}

def clean_text(text):
    return text.replace("\\n", " ").strip()

response = requests.get(URL)
lines = response.text.splitlines()

filtered_lines = []
inside_event = False
skip_event = False
event_lines = []

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside_event = True
        skip_event = False
        event_lines = []

    if inside_event:
        event_lines.append(line)

        # titolo evento
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
            summary_lower = summary.lower()

            # escludi corso diseases dal calendario personale
            if FILTER_TEXT.lower() in summary_lower:
                skip_event = True

            for course, info in TARGET_COURSES.items():
                if course in summary_lower:
                    new_title = f"{info['emoji']} {info['title']}"
                    event_lines[-1] = f"SUMMARY:{new_title}"

        # descrizione → aula + docente
        if line.startswith("DESCRIPTION:"):
            desc = clean_text(line.replace("DESCRIPTION:", ""))

            room_match = re.search(r"Aula\s+[A-Za-z0-9\. ]+", desc)
            room = room_match.group(0) if room_match else ""

            prof_match = re.search(r"\((.*?)\)", desc)
            professor = prof_match.group(1) if prof_match else ""

            new_desc = " — ".join(filter(None, [room, professor]))
            event_lines[-1] = f"DESCRIPTION:{new_desc}"

        if line.startswith("END:VEVENT"):
            inside_event = False
            if not skip_event:
                filtered_lines.extend(event_lines)

    else:
        filtered_lines.append(line)

with open("filtered_calendar.ics", "w") as f:
    f.write("\n".join(filtered_lines))

print("Calendario aggiornato con titoli brevi e formattazione!")
