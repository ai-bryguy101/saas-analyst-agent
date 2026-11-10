"""Meeting transcripts: WebVTT (Zoom-style) and plain-text (Teams-style) with auto-caption errors."""
from __future__ import annotations

from datetime import date, timedelta

from ..util import AS_OF, rand_date, rng_for, write_text

FILLER = ["Can everyone hear me?", "Sorry, I was on mute.", "Let's give people one more minute.", "Can you share your screen?",
          "I'll take that offline.", "Next slide please.", "We're at time, let's wrap.", "I think you froze for a second.",
          "Um, so, yeah.", "Let me pull that up.", "Is the recording on?", "Can we park that?"]
TOPICS = {
    "pipeline": ["We have {n} deals in commit for the quarter.", "The {comp} deal slipped to next quarter.",
                 "Discounting is creeping up, average is around {pct} percent.", "Can RevOps clean up the stale opportunities?"],
    "support": ["Backlog is at {n} tickets.", "Mobile sync is still the top driver.", "CSAT dipped after the release.",
                "We need another tier two hire."],
    "eng": ["The migration to AWS is {pct} percent done.", "We're seeing replica lag again.", "Release train moves to every two weeks.",
            "Postmortem for last week's incident is in Confluence."],
    "finance": ["Collections are slow in Canada.", "DSO is {n} days.", "The FX hit on the UK numbers was bigger than plan.",
                "Please don't quote the CRM ARR field to anyone."],
}


def ts(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{0:03d}"


def asr(r, text):
    """Auto-caption errors."""
    subs = {"Brindle": "Brindle" if r.random() > 0.3 else "Brindled", "Kestrel": r.choice(["Kestrel", "kestrel", "Kessel"]),
            "Meridian": r.choice(["Meridian", "Meridien"]), "ARR": r.choice(["ARR", "a r r", "air"]), "Classic": r.choice(["Classic", "classic"]),
            "twenty five": r.choice(["twenty five", "25", "twenty-five"])}
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def vtt(cues):
    out = ["WEBVTT", ""]
    for i, (start, end, spk, text) in enumerate(cues, 1):
        out += [str(i), f"{ts(start)} --> {ts(end)}", f"<v {spk}>{text}", ""]
    return "\n".join(out)


def render(world, out, seed):
    r = rng_for(seed, "meetings")
    base = out / "meetings"
    P = {p.pid: p for p in world.people}

    # ---------------------------------------------------------------- GF08: exec staff 2019-11-14
    script = [
        ("E001", "Okay, let's start. Main item is Classic end of life."),
        ("E003", "I ran the model over the weekend. At twenty percent credit we lose too many of the government sites. At twenty five percent for twelve months we keep most of them and it pays back in year two."),
        ("E004", "Sales is fine with twenty five. Twenty was a non-starter for the counties."),
        ("E006", "Engineering can't support Classic past mid next year anyway. The 4.x installs don't run on the new Windows server."),
        ("E001", "So the date is June thirtieth, twenty twenty. Hard stop. No license renewals, no patches after that."),
        ("E005", "And the credit applies to the cloud subscription fees for the first twelve months, only if they move before the date?"),
        ("E001", "Yes. Twenty five percent, twelve months, migrate before June thirty. I'll send the final note next week. Ignore the draft memo."),
        ("E003", "Classic maintenance invoices stop with the Q2 quarter then."),
        ("E004", "One more thing, Tri-County Public Works asked if they can go early. I'd like to give them the credit too."),
        ("E001", "Fine. Next item: Kestrel diligence. We're not ready to talk about that yet, keep it in this room."),
    ]
    cues, t = [], 4
    for pid, line in script:
        dur = max(3, len(line) // 14)
        cues.append((t, t + dur, P[pid].name, asr(r, line)))
        t += dur + r.randint(1, 4)
        if r.random() < 0.3:
            cues.append((t, t + 2, P[r.choice(["E003", "E005", "E006"])].name, r.choice(FILLER)))
            t += 3
    write_text(base / "2019-11-14_exec-staff.vtt", vtt(cues))

    # ---------------------------------------------------------------- filler meetings
    kinds = list(TOPICS)
    people = world.people
    for _ in range(36):
        d = rand_date(r, date(2020, 3, 16), AS_OF)   # remote meetings started being recorded in 2020
        kind = r.choice(kinds)
        attendees = r.sample([p for p in people if p.hired <= d and (not p.left or p.left >= d)] or people, 4)
        cues, t = [], 2
        for _ in range(r.randint(18, 45)):
            spk = r.choice(attendees)
            line = r.choice(TOPICS[kind] + FILLER).format(n=r.randint(3, 400), pct=r.randint(5, 95), comp=r.choice(world.customers).name)
            dur = max(2, len(line) // 14)
            cues.append((t, t + dur, spk.name if r.random() > 0.05 else "Unknown Speaker", asr(r, line)))
            t += dur + r.randint(0, 6)
        if r.random() < 0.5:
            write_text(base / f"{d}_{kind}-sync.vtt", vtt(cues))
        else:
            txt = [f"{kind.title()} sync - {d:%A, %B %d, %Y}", "Transcript", ""]
            for start, _, spk, text in cues:
                txt += [f"{spk}   {start // 60}:{start % 60:02d}", text, ""]
            write_text(base / f"{d}_{kind}-sync_transcript.txt", "\n".join(txt), encoding="utf-8", bom=True, newline="\r\n")
    return {}
