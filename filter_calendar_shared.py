import requests

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

    if inside:
        event.append(line)

    if line.startswith("END:VEVENT"):
        inside = False

        text_block = " ".join(event).lower()
        course_found = None

        for key in COURSES:
            if key in text_block:
                course_found = key
                break

        new_event = []

        for e in event:
            if e.startswith("SUMMARY:") and course_found:
                new_event.append(f"SUMMARY:{COURSES[course_found]}")
            else:
                new_event.append(e)

        output.extend(new_event)

    elif not inside:
        output.append(line)

with open("shared_calendar.ics", "w") as f:
    f.write("\n".join(output))

print("Shared calendar restored ✅")
