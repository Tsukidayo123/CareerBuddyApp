# careerbuddy/build/single_file_builder.py
import pathlib, zipapp

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = PROJECT_ROOT / "CareerBuddyDemo.pyz"

def build():
    # This will bundle everything *except* the .venv or any __pycache__.
    zipapp.create_archive(
        source=str(PROJECT_ROOT),
        target=str(TARGET),
        interpreter="/usr/bin/env python3",
        main="careerbuddy.app:main",
    )
    # Rename to .py so the employer can just double‑click
    demo_py = TARGET.with_suffix('.py')
    demo_py.write_bytes(TARGET.read_bytes())
    print(f"✅ Demo built: {demo_py}")

if __name__ == "__main__":
    build()
