import re

SOURCE_FILE = "shared_calendar.ics"

COURSES = {
    "data_science.ics": ("data science in healthcare", "📊 Data Science"),
    "diseases.ics": ("diseases classification and mechanisms", "🦠 Diseases"),
    "foundations.ics": ("foundations of medical research", "🔬 Foundations"),
    "medical_informatics.ics": ("medical informatics", "💻 Med Info"),
}

with open(SOURCE_FILE, "r") as f:
    lines = f.readlines()

header = []
footer = []
events = {k: [] for k in COURSES}
inside_event = False
block = []

for line in lines:

    if line.startswith("BEGIN:VEVENT"):
        inside_event = True
        block = [line]
        continue

    if line.startswith("END:VEVENT"):
        block.append(line)
        inside_event = False
        text = "".join(block).lower()

        for filename, (keyword, new_title) in COURSES.items():
            if keyword in text:

                new_block = []
                for l in block:
                    if l.startswith("SUMMARY:"):
                        new_block.append("SUMMARY:" + new_title + "\n")
                    else:
                        new_block.append(l)

                events[filename].extend(new_block)

        continue

    if inside_event:
        block.append(line)
    else:
        if line.startswith("END:VCALENDAR"):
            footer.append(line)
        else:
            header.append(line)

# scrittura file
for filename in COURSES:
    with open(filename, "w") as f:
        for h in header:
            f.write(h)
        for ev in events[filename]:
            f.write(ev)
        for ft in footer:
            f.write(ft)

print("Single-course calendars generated with short titles!")
