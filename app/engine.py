import re

from .knowledge import TOPICS, tokens
from .providers import SourceUnavailable
from .schemas import ChatResponse

TEXT = {
    "en": {
        "found": "Here are relevant passages from the available sources. Read each passage with its surrounding context; published translations and translator footnotes are shown below.",
        "hadith": "Here are relevant Hadith references with original explanatory summaries. These summaries are not verbatim translations.",
        "missing": "I could not find a verified source for this question. Try a Quran reference such as 2:177, a surah name, or a supported topic. The Hadith library currently contains five selected summaries; I cannot verify other Hadiths or search arbitrary websites.",
        "invalid": "That Quran reference is invalid. Please provide a chapter from 1–114 and a verse within that chapter.",
        "limit": "Please request at most 20 verses at a time, for example 2:1-20. I will not silently shorten a requested passage.",
        "api_failed": "The approved source API could not be reached or verified. No unverified text has been substituted.",
        "external_off": "The passage is unavailable locally and external lookup is disabled.",
        "model_unavailable": "The optional local model is unavailable. The retrieved source passages remain available.",
        "model_rejected": "The optional model response failed citation or format checks. Showing the retrieved sources instead.",
        "ruling": "For a personal religious ruling, consult a qualified scholar who can consider your circumstances and school of interpretation.",
    },
    "hi": {
        "found": "उपलब्ध स्रोतों से संबंधित आयतें नीचे दी गई हैं। आयतों को उनके संदर्भ के साथ पढ़ें। प्रकाशित भावार्थ और अनुवादक की टिप्पणियाँ अलग से दिखाई गई हैं।",
        "hadith": "नीचे संबंधित हदीसों के संदर्भ और व्याख्यात्मक सार दिए गए हैं। ये सार शब्दशः अनुवाद नहीं हैं।",
        "missing": "इस प्रश्न के लिए मुझे प्रमाणित स्रोत नहीं मिला। 2:177 जैसा क़ुरआन का संदर्भ, किसी सूरह का नाम या समर्थित विषय पूछें। हदीस संग्रह में अभी पाँच चयनित सार हैं; मैं अन्य हदीसों को सत्यापित नहीं कर सकता या किसी भी वेबसाइट पर खोज नहीं कर सकता।",
        "invalid": "यह क़ुरआन संदर्भ सही नहीं है। कृपया 1–114 के बीच सूरह और उसमें मौजूद आयत का नंबर दें।",
        "limit": "एक बार में अधिकतम 20 आयतें पूछें, जैसे 2:1-20। माँगे गए अंश को बिना बताए छोटा नहीं किया जाएगा।",
        "api_failed": "अनुमोदित स्रोत API से संपर्क या स्रोत की पुष्टि नहीं हो सकी। कोई अप्रमाणित पाठ नहीं दिया गया है।",
        "external_off": "यह अंश स्थानीय संग्रह में उपलब्ध नहीं है और बाहरी खोज बंद है।",
        "model_unavailable": "वैकल्पिक स्थानीय मॉडल उपलब्ध नहीं है। स्रोतों से प्राप्त पाठ नीचे उपलब्ध हैं।",
        "model_rejected": "मॉडल का उत्तर संदर्भ या प्रारूप की जाँच में सफल नहीं हुआ। नीचे प्रमाणित स्रोत दिखाए गए हैं।",
        "ruling": "व्यक्तिगत धार्मिक निर्णय के लिए योग्य विद्वान से सलाह लें, जो आपकी परिस्थितियों और व्याख्या की परंपरा पर विचार कर सके।",
    },
}

ALIASES = {1: ("fatiha", "faatiha", "फ़ातिहा", "फातिहा", "فاتحة"), 112: ("ikhlas", "ikhlaas", "इख़लास", "इखलास", "إخلاص"), 113: ("falaq", "फलक", "फ़लक"), 114: ("an-nas", "an nas", "naas", "नास")}


class Engine:
    def __init__(self, knowledge, api, model, settings):
        self.knowledge = knowledge
        self.api = api
        self.model = model
        self.settings = settings

    async def answer(self, request):
        question = request.question
        language = request.language
        # Honor explicit language requests as well as the interface preference.
        if re.search(r"\b(in|into) hindi\b|हिंदी में|हिन्दी में", question.lower()):
            language = "hi"
        elif re.search(r"\b(in|into) english\b|अंग्रेज़ी में|अंग्रेजी में", question.lower()):
            language = "en"
        if request.context_question and re.fullmatch(r"(?:please\s+)?(?:translate\s+(?:that|it)\s+(?:into|to)\s+)?(?:in\s+)?(?:hindi|english)(?:\s+please)?[?.!]*|(?:हिंदी|हिन्दी|अंग्रेज़ी|अंग्रेजी)\s*में[।?]*", question.lower()):
            language = "hi" if re.search(r"hindi|हिंदी|हिन्दी", question.lower()) else "en"
            question = request.context_question
        wording = TEXT[language]
        evidence = []
        notices = []
        error = None
        scope = request.scope
        if scope == "all":
            asks_hadith = bool(re.search(r"\bhadiths?\b|हदीस", question.lower()))
            asks_quran = bool(re.search(r"\bqur'?an\b|क़?ुरआन", question.lower()))
            if asks_hadith and not asks_quran:
                scope = "hadith"
            elif asks_quran and not asks_hadith:
                scope = "quran"
        references = []
        matches = list(re.finditer(r"(?<!\d)(\d{1,3})\s*[:：]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?(?!\d)", question))
        if scope != "hadith":
            for match in matches:
                chapter, first = int(match[1]), int(match[2])
                last = int(match[3]) if match[3] else first
                if last < first or not self.knowledge.valid_reference(chapter, first) or not self.knowledge.valid_reference(chapter, last):
                    error = "invalid"
                    break
                if last - first + 1 > 20:
                    error = "limit"
                    break
                references.extend((chapter, v) for v in range(first, last + 1))
            if not matches:
                lower = question.lower()
                chapter = next((c for c, names in ALIASES.items() if any(name in lower for name in names)), None)
                numeric = re.search(r"\b(?:surah|sura|chapter)\s+(\d{1,3})\b|सूर[हा़]*\s+(\d{1,3})", lower)
                if numeric:
                    chapter = int(numeric[1] or numeric[2])
                if chapter:
                    if chapter not in self.knowledge.chapters:
                        error = "invalid"
                    elif self.knowledge.chapters[chapter]["total_verses"] > 20:
                        error = "limit"
                    else:
                        references = [(chapter, v) for v in range(1, self.knowledge.chapters[chapter]["total_verses"] + 1)]
            references = list(dict.fromkeys(references))
            if len(references) > 20:
                error = "limit"
            if references and not error:
                missing = []
                found = {}
                for ref in references:
                    entry = self.knowledge.verse(*ref, language)
                    if entry:
                        found[ref] = entry
                    else:
                        missing.append(ref)
                if missing:
                    if request.allow_external and self.settings.external_enabled:
                        try:
                            remote = await self.api.verses(missing, language)
                            for entry in remote:
                                _, c, v = entry.id.split("-")
                                found[(int(c), int(v))] = entry
                        except SourceUnavailable:
                            error = "api_failed"
                    else:
                        error = "external_off"
                # A passage is either complete or explicitly unavailable; no partial quote.
                if not error:
                    evidence = [found[ref] for ref in references]
        hadith_reference = re.search(r"\b(bukhari|muslim)(?:\s*[:#]?\s*)(\d+)([a-z]?)\b", question.lower())
        if hadith_reference and request.scope != "quran":
            collection, number, suffix = hadith_reference.groups()
            id = f"{collection}-{number}{suffix or ('a' if collection == 'muslim' and number == '612' else '')}"
            entry = self.knowledge.hadith_entry(id, language)
            evidence = [entry] if entry else []
        if not evidence and not references and not error and not hadith_reference and not matches:
            query_tokens = set(tokens(question))
            for keywords, verses, hadith_ids in TOPICS:
                if query_tokens & keywords:
                    if scope != "hadith":
                        evidence.extend(self.knowledge.verse(*ref, language) for ref in verses)
                    if scope != "quran":
                        evidence.extend(self.knowledge.hadith_entry(id, language) for id in hadith_ids)
            if not evidence and scope != "hadith":
                evidence = self.knowledge.search(question, language)
            if not evidence and scope == "hadith":
                evidence = [self.knowledge.hadith_entry(h["id"], language) for h in self.knowledge.hadith if set(tokens(h[language])) & query_tokens]
        evidence = list({s.id: s for s in evidence if s is not None}.values())[:20]
        if error or not evidence:
            return ChatResponse(query=request.question, retrieval_query=question, response=wording[error or "missing"], language=language, citations=[], mode="no_sources", source_mode="none", model_status="disabled")
        response = wording["hadith"] if all(s.kind == "hadith" for s in evidence) else wording["found"]
        summary, model_status = await self.model.summarize(question, language, evidence)
        if summary:
            response = summary
        elif model_status in {"unavailable", "rejected"}:
            notices.append(wording["model_" + model_status])
        if re.search(r"fatwa|divorce|inheritance|is it halal|is it haram|तलाक|फ़तवा|फतवा|विरासत", question.lower()):
            notices.append(wording["ruling"])
        origins = {s.origin for s in evidence}
        source_mode = "mixed" if len(origins) > 1 else origins.pop()
        return ChatResponse(query=request.question, retrieval_query=question, response=response, language=language, citations=evidence, mode="model" if summary else "retrieval", source_mode=source_mode, model_status=model_status, notices=notices)
