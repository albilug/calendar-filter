import requests

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

COURSES = {
    "data science in healthcare": ("📊", "Data Science"),
    "foundations of medical research": ("🔬", "Foundations"),
    "medical informatics": ("💻", "Med Info"),
    "diseases classification and mechanisms": ("🦠", "Diseases"),
}

response = requests.get(URL)

if response.status_code != 200:
    raise Exception("Blackboard calendar download failed")

lines = response.text.splitlines()

output = []
event = []
inside_event = False

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside_event = True
        event = [line]
        continue

    if inside_event:
        event.append(line)

        if line.startswith("END:VEVENT"):
            inside_event = False

            text = " ".join(event).lower()
            course_found = None

            for key in COURSES:
                if key in text:
                    course_found = key
                    break

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

        continue

    output.append(line)

with open("shared_calendar.ics", "w") as f:
    f.write("\n".join(output))

print("Shared calendar updated!")
