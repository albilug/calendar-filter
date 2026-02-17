import requests
import re

URL = "https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics"

COURSES = {
    "data science": ("data_science.ics", "📊 Data Science in Healthcare"),
    "foundations": ("foundations.ics", "🔬 Foundations of Medical Research"),
    "medical informatics": ("medical_informatics.ics", "💻 Medical Informatatics"),
    "diseases classification": ("diseases.ics", "🦠 Diseases Classification and Mechanisms"),
}

response = requests.get(URL)
lines = response.text.splitlines()

events = {key: [] for key in COURSES}
header = []
footer = []
inside_event = False
block = []

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside_event = True
        block = []

    if inside_event:
        block.append(line)
    else:
        header.append(line)

    if line.startswith("END:VEVENT"):
        inside_event = False

        summary = ""
        description = ""

        for l in block:
            if l.startswith("SUMMARY:"):
                summary = l.replace("SUMMARY:", "")
            if l.startswith("DESCRIPTION:"):
                description = l.replace("DESCRIPTION:", "")

        desc_lower = description.lower()

        for key in COURSES:
            if key in desc_lower:

                filename, title = COURSES[key]

                teacher = ""
                match = re.search(r"\((.*?)\)", description)
                if match:
                    teacher = match.group(1)

                new_block = []
                for l in block:
                    if l.startswith("SUMMARY:"):
                        new_block.append("SUMMARY:" + title)
                    elif l.startswith("DESCRIPTION:"):
                        desc = f"Aula: {summary}"
                        if teacher:
                            desc += f"\\nDocente: {teacher}"
                        new_block.append("DESCRIPTION:" + desc)
                    else:
                        new_block.append(l)

                events[key].extend(new_block)

# scrive i file
for key, (filename, title) in COURSES.items():
    with open(filename, "w") as f:
        for h in header:
            f.write(h + "\n")
        for line in events[key]:
            f.write(line + "\n")
