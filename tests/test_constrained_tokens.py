from lmformatenforcer import CharacterLevelParserConfig, JsonSchemaParser

from app.constrained_tokens import build_tokenizer_data, prefix_function


class TinyTokenizer:
    """A Hindi word token contains characters absent from token-start letters."""
    vocab = [chr(i) for i in range(128)] + ["दान।"]
    eos_token_id = 0
    all_special_ids = [0]

    def __len__(self):
        return len(self.vocab)

    def encode(self, text):
        return [ord(c) for c in text]

    def decode(self, ids):
        return ''.join(self.vocab[i] for i in ids)


class TokenIds(list):
    def tolist(self):
        return list(self)


def test_hindi_word_and_danda_do_not_prematurely_end_structured_generation():
    tokenizer = TinyTokenizer()
    config = CharacterLevelParserConfig()
    config.alphabet += ''.join(chr(i) for i in range(0x0900, 0x0980))
    parser = JsonSchemaParser({"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False}, config=config)
    allowed = prefix_function(build_tokenizer_data(tokenizer), parser)
    prompt = tokenizer.encode('explain charity')
    prefix = TokenIds(prompt)
    for token in tokenizer.encode('{"summary":"'):
        assert token in allowed(0, prefix)
        prefix.append(token)
    assert 128 in allowed(0, prefix)
    prefix.append(128)
    # Previously the parser lost Devanagari characters and allowed EOS here,
    # leaving the JSON object unfinished after a valid Hindi word.
    assert tokenizer.eos_token_id not in allowed(0, prefix)
    for token in tokenizer.encode('"}'):
        assert token in allowed(0, prefix)
        prefix.append(token)
    assert tokenizer.eos_token_id in allowed(0, prefix)
