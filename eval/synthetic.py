from __future__ import annotations

import random

from engine.features.text import minhash_signature
from engine.schema import Feature, Item

VOCAB = [f"slowo{i}" for i in range(400)]
TOPICS = ["investment", "health", "gambling", "shopping", "news"]
PERSONS = [f"Osoba Publiczna {i}" for i in range(6)]


def _feat(name: str, value, conf: float = 0.9) -> Feature:
    return Feature(name, name.split(".")[0], value, conf, "korpus syntetyczny")


def _phash(rnd: random.Random) -> str:
    return f"{rnd.getrandbits(64):016x}"


def _flip(h: str, bits: int, rnd: random.Random) -> str:
    v = int(h, 16)
    for b in rnd.sample(range(64), bits):
        v ^= 1 << b
    return f"{v:016x}"


def _mutate_words(words: list[str], frac: float, rnd: random.Random) -> list[str]:
    out = list(words)
    for i in rnd.sample(range(len(out)), int(len(out) * frac)):
        out[i] = rnd.choice(VOCAB)
    return out


def synthetic_corpus(
    campaigns: int = 8, per_campaign: int = 4, singles: int = 6, seed: int = 7, decoys: bool = True
) -> tuple[list[Item], dict[str, str]]:
    rnd = random.Random(seed)
    items: list[Item] = []
    truth: dict[str, str] = {}
    stock = [_phash(rnd) for _ in range(campaigns // 2 + 1)]
    for c in range(campaigns):
        story = [rnd.choice(VOCAB) for _ in range(120)]
        title = sorted(set(rnd.sample(VOCAB, 5)))
        images = [_phash(rnd) for _ in range(4)]
        tracker = f"fbpixel:{rnd.randrange(10**9)}"
        phone = f"phone:{rnd.randrange(500000000, 799999999)}"
        topic = TOPICS[c % len(TOPICS)]
        person = PERSONS[(c // 2) % len(PERSONS)] if decoys else PERSONS[c % len(PERSONS)]
        product = f"produkt{c}"
        for k in range(per_campaign):
            case = f"s{c}_{k}"
            iid = case if k % 2 == 0 else f"{case}/strona_1"
            mode = k % 4
            feats: dict[str, Feature] = {"text.topic": _feat("text.topic", [topic])}
            if mode in (0, 1, 2):
                words = _mutate_words(story, 0.15 + 0.1 * rnd.random(), rnd)
                feats["text.narrative"] = _feat(
                    "text.narrative",
                    {"minhash": minhash_signature(words), "tokens": len(words), "preview": ""},
                )
                feats["text.title"] = _feat(
                    "text.title", sorted(set(_mutate_words(title, 0.4, rnd)))
                )
                feats["text.entities"] = _feat("text.entities", sorted({product, person.lower()}))
                feats["person.names"] = _feat("person.names", [person])
            if mode in (0, 2, 3):
                chosen = rnd.sample(images, 2)
                if decoys:
                    chosen.append(stock[c // 2])
                feats["visual.assets"] = _feat(
                    "visual.assets",
                    [
                        {"src": f"{iid}/img{j}.png", "phash": _flip(h, rnd.randrange(0, 5), rnd)}
                        for j, h in enumerate(chosen)
                    ],
                )
            if mode in (1, 3) or rnd.random() < 0.3:
                feats["infra.tracker_ids"] = _feat("infra.tracker_ids", [tracker])
            if mode == 2:
                feats["text.identifiers"] = _feat("text.identifiers", [phone])
            items.append(
                Item(id=iid, case_id=case, paths={"html": [f"{iid}/x.html"]}, features=feats)
            )
            truth[iid] = f"C{c}"
    for s in range(singles):
        story = [rnd.choice(VOCAB) for _ in range(120)]
        iid = f"solo{s}"
        items.append(
            Item(
                id=iid,
                case_id=iid,
                paths={"html": [f"{iid}/x.html"]},
                features={
                    "text.topic": _feat("text.topic", [TOPICS[s % len(TOPICS)]]),
                    "person.names": _feat("person.names", [PERSONS[s % len(PERSONS)]]),
                    "text.narrative": _feat(
                        "text.narrative",
                        {"minhash": minhash_signature(story), "tokens": 120, "preview": ""},
                    ),
                    "visual.assets": _feat(
                        "visual.assets", [{"src": f"{iid}/a.png", "phash": _phash(rnd)}]
                    ),
                },
            )
        )
        truth[iid] = f"S{s}"
    return items, truth
