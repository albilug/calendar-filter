import requests

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796ccca$"

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
        course_found = None
        skip_event = False

    if inside:
        event.append(line)

        low = line.lower()

        # individua il corso dal contenuto
        for key in COURSES:
            if key in low:
                course_found = key

        # elimina eventi aula e roba inutile
        if line.startswith("SUMMARY:Aula"):
            skip_event = True

        if "hexagonal binned plot" in low:
            skip_event = True

    if line.startswith("END:VEVENT"):
        inside = False

        # se non è un corso valido → scarta
        if skip_event or not course_found:
            continue

        emoji, short = COURSES[course_found]

        new_event = []
        for e in event:
            if e.startswith("SUMMARY:"):
                new_event.append(f"SUMMARY:{emoji} {short}")
            else:
                new_event.append(e)

        output.extend(new_event)

    elif not inside:
        output.append(line)

with open("shared_calendar.ics", "w") as f:
    f.write("\n".join(output))

print("Shared calendar cleaned and updated!")
