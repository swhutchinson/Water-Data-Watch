# A control this project runs on itself: before anything is pushed, search the files git would publish for private words.
# The word list stays on this PC and is never committed, so the check simply says so if the list is missing.
# Usage: python tools/check_public.py [extra folder to scan, such as data/pub]

# Reads the command line.
import sys
# Runs git to get the list of files it would publish.
import subprocess
# Handles file paths.
from pathlib import Path

# The project folder, one level above this script.
ROOT = Path(__file__).resolve().parent.parent
# The private list of words that must never appear in public.
WORDS_FILE = ROOT / "_work" / "forbidden_words.txt"
# Folders and files git must always ignore, because they are private.
MUST_BE_IGNORED = ["_work/forbidden_words.txt", "HANDOVER_WATER_DATA_QUALITY.md", "NEXT_SESSION_PROMPT.txt", "SOURCES_STARTER.md", "recon/FINDINGS_2026-11-04.md", "starter/README.md"]

# Stop with a clear message if the word list is not on this machine.
if not WORDS_FILE.exists():
    # Say what is missing and fail, so a skipped check is never mistaken for a pass.
    raise SystemExit("Not checked: the private word list is missing, so nothing has been proved clean.")
# Read the words, ignoring blank lines.
words = [w.strip().lower() for w in WORDS_FILE.read_text(encoding="utf-8").splitlines() if w.strip()]
# Ask git for every file that is tracked or would be added.
listing = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
# Turn the listing into file paths.
files = [ROOT / line for line in listing.splitlines() if line.strip()]
# Add any extra folder named on the command line, such as the data branch checked out locally.
for extra in sys.argv[1:]:
    # Every file under that folder, skipping git's own files.
    files += [p for p in Path(extra).rglob("*") if p.is_file() and ".git" not in p.parts]
# Problems found so far.
problems = []
# Check each private file really is ignored.
for name in MUST_BE_IGNORED:
    # Ask git whether it ignores this path.
    ignored = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0
    # A private file that git would publish is a problem.
    if not ignored:
        # Record which file.
        problems.append(f"NOT IGNORED: {name}")
# Check every public file for every private word.
for path in files:
    # Skip anything that has disappeared since the listing, and big binary files.
    if not path.is_file() or path.suffix in {".png", ".webp", ".parquet", ".gz", ".ico"}:
        # Move on to the next file.
        continue
    # Read the file as text, ignoring characters that can't be read.
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    # Try each word.
    for word in words:
        # A hit is a problem. The word itself isn't printed, in case this output is shared.
        if word in text:
            # Record the file and which line of the list matched.
            problems.append(f"PRIVATE WORD (list line {words.index(word) + 1}): {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
# Report any problems and fail.
if problems:
    # One line per problem.
    print("\n".join(problems))
    # A non-zero exit stops the push.
    raise SystemExit(1)
# Say what was checked.
print(f"Clean: {len(files)} public files checked against {len(words)} private words.")
