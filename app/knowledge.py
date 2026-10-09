"""Local Quran retrieval. Original source strings are never normalized for display."""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter

from .schemas import Evidence

STOP = set("what does do the a an in of on to about is are can you me please tell translate translation quran qur'an surah says say verse hadith hadiths english hindi into and it for from with how when that this explain meaning".split())
STOP |= {"के", "की", "का", "में", "है", "हैं", "क्या", "और", "से", "को", "पर", "एक", "बताएं", "बताएँ", "हिंदी", "अनुवाद", "कुरआन", "क़ुरआन", "हदीस", "बारे", "करें"}
STOP |= {"who", "why", "where", "which", "find", "give", "show", "us", "mentioned", "mentions", "according"}

TOPICS = [
    ({"charity", "zakat", "zakah", "sadaqah", "sadaqa", "donation", "दान", "ज़कात", "जकात", "सदक़ा", "खैरात"}, [(2, 177), (2, 261), (2, 262)], ["bukhari-1410"]),
    ({"prayer", "salah", "salat", "namaz", "नमाज़", "नमाज", "नमाज़ों", "प्रार्थना"}, [(4, 103), (2, 43)], ["muslim-612a", "bukhari-528"]),
    ({"fasting", "fast", "ramadan", "roza", "रोज़ा", "रोजा", "रमज़ान", "उपवास"}, [(2, 183), (2, 185)], []),
    ({"mercy", "forgiveness", "forgive", "repentance", "तौबा", "क्षमा", "दया"}, [(39, 53), (2, 286)], []),
    ({"patience", "sabr", "सब्र", "धैर्य"}, [(2, 153), (94, 5), (94, 6)], []),
    ({"intention", "intentions", "niyyah", "नीयत", "नियत"}, [], ["bukhari-1"]),
    ({"brotherhood", "kindness", "भाईचारा"}, [(49, 13)], ["bukhari-13"]),
    ({"parents", "parent", "माता", "पिता", "माँ", "मां"}, [(17, 23), (17, 24)], []),
    ({"knowledge", "ज्ञान", "इल्म"}, [(17, 36), (20, 114)], []),
]


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    return [w for w in re.findall(r"[a-z]+|[\u0900-\u097f]+|[\u0621-\u064a]+", text) if w not in STOP and len(w) > 1]


class Knowledge:
    def __init__(self, data_dir):
        self.manifest = json.loads((data_dir / "manifest.json").read_text())
        for file, expected in self.manifest["checksums"].items():
            if hashlib.sha256((data_dir / file).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Source integrity check failed: {file}")
        self.chapters = {c["id"]: c for c in json.loads((data_dir / "chapters.json").read_text())["chapters"]}
        self.corpora = {lang: json.loads((data_dir / file).read_text()) for lang, file in [("ar", "arabic.json"), ("en", "english.json"), ("hi", "hindi.json")]}
        self.editions = {e["lang"]: e for e in self.manifest["translations"]}
        self.hadith = json.loads((data_dir / "hadith.json").read_text())
        self.index = {}
        self.frequency = {}
        self.average_length = {}
        for lang, corpus in self.corpora.items():
            docs = {}
            df = Counter()
            for chapter, verses in corpus.items():
                if len(verses) != self.chapters[int(chapter)]["total_verses"]:
                    raise ValueError(f"Incomplete {lang} chapter {chapter}")
                for v in verses:
                    if not v["text"] or v["chapter"] != int(chapter):
                        raise ValueError("Invalid source record")
                    key = (v["chapter"], v["verse"])
                    docs[key] = Counter(tokens(v["text"]))
                    df.update(docs[key].keys())
            if len(docs) != 6236:
                raise ValueError(f"Incomplete {lang} corpus")
            self.index[lang] = docs
            self.frequency[lang] = df
            self.average_length[lang] = sum(sum(c.values()) for c in docs.values()) / len(docs)

    def verse(self, chapter, verse, language):
        if not self.valid_reference(chapter, verse):
            return None
        ar = self.corpora["ar"].get(str(chapter), [])
        translated = self.corpora[language].get(str(chapter), [])
        if len(ar) < verse or len(translated) < verse:
            return None
        edition = self.editions[language]
        entry = translated[verse - 1]
        return Evidence(
            id=f"quran-{chapter}-{verse}", reference=f"Quran {chapter}:{verse} · {self.chapters[chapter]['transliteration']}",
            kind="quran", arabic=ar[verse - 1]["text"], text=entry["text"], footnotes=entry.get("footnotes", ""),
            url=f"https://quranenc.com/en/browse/{edition['key']}/{chapter}#{verse}",
            publisher=edition["title"] + " / QuranEnc.com; Arabic: Tanzil Project", version=edition["version"],
            license="QuranEnc republication terms; Arabic: CC BY 3.0 (verbatim)",
            license_url=self.manifest["translation_terms"]["url"],
            note="Published translation of the meanings; translator footnotes are kept separately.",
        )

    def hadith_entry(self, id, language):
        item = next((h for h in self.hadith if h["id"] == id), None)
        if not item:
            return None
        return Evidence(
            id=id, reference=item["reference"], kind="hadith", text=item[language], url=item["url"],
            publisher="Noor · original explanatory summary", version="1.0", license="MIT (original summary only)",
            license_url="https://opensource.org/license/mit", note=item["note"],
        )

    def valid_reference(self, chapter, verse):
        return chapter in self.chapters and 1 <= verse <= self.chapters[chapter]["total_verses"]

    def search(self, question, language, limit=3):
        # Search both the query's script and preferred response language.
        query_language = "hi" if re.search(r"[\u0900-\u097f]", question) else "ar" if re.search(r"[\u0600-\u06ff]", question) else "en"
        query = set(tokens(question))
        if not query:
            return []
        docs = self.index[query_language]
        df = self.frequency[query_language]
        # Ignore generic terms that would retrieve a verse unrelated to the actual question.
        original_count = len(query)
        query = {w for w in query if df[w] and df[w] < len(docs) * 0.4}
        if len(query) < original_count:
            return []
        if not query:
            return []
        ranked = []
        for key, counts in docs.items():
            matched = query & counts.keys()
            if len(matched) < max(1, math.ceil(len(query) * .6)):
                continue
            length = sum(counts.values())
            score = sum(math.log(1 + (len(docs) - df[w] + .5) / (df[w] + .5)) * counts[w] * 2.2 / (counts[w] + 1.2 * (.25 + .75 * length / self.average_length[query_language])) for w in matched)
            ranked.append((score, key))
        ranked.sort(reverse=True)
        return [self.verse(*key, language) for _, key in ranked[:limit]]
