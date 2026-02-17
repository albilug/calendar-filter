import requests
import re

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

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

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside = True
        event = []
        description = ""

    if inside:
        event.append(line)

        if line.startswith("DESCRIPTION:"):
            description = line.lower()

        if line.startswith("END:VEVENT"):
            inside = False

            course_found = None
            for key in COURSES:
                if key in description:
                    course_found = key
                    break
            # elimina eventi aula separati
            if any(line.startswith("SUMMARY:Aula") for line in event):
                continue
            if course_found:
                emoji, short = COURSES[course_found]

                new_event = []
                for e in event:
                    if e.startswith("SUMMARY:"):
                        new_event.append(f"SUMMARY:{emoji} {short}")
                    else:
                        new_event.append(e)

                output.extend(new_event)
            else:
                output.extend(event)

    else:
        output.append(line)

with open("shared_calendar.ics", "w") as f:
    f.write("\n".join(output))

print("Shared calendar titles fixed!")
