"""Transformers 5 adapter for LM Format Enforcer's public token API.

Tokenizer construction follows lm-format-enforcer 0.11.3's MIT-licensed
Transformers integration. Its legacy PreTrainedTokenizerBase import moved in
Transformers 5. The low-level API avoids importing that incompatible adapter.
See deploy/licenses/LM-FORMAT-ENFORCER-MIT.txt for the preserved license.
"""

from functools import partial

from lmformatenforcer import TokenEnforcer, TokenEnforcerTokenizerData


def decode_tokens(tokenizer, ids):
    # A byte-level token may end in an incomplete Unicode character.
    return tokenizer.decode(ids).rstrip('�')


def build_tokenizer_data(tokenizer):
    zero = tokenizer.encode("0")[-1]
    special = set(tokenizer.all_special_ids)
    vocab_size = len(tokenizer)
    tokens = []
    for token_id in range(vocab_size):
        if token_id in special:
            continue
        after_zero = tokenizer.decode([zero, token_id])[1:]
        regular = tokenizer.decode([token_id])
        tokens.append((token_id, after_zero, len(after_zero) > len(regular)))
    return TokenEnforcerTokenizerData(tokens, partial(decode_tokens, tokenizer), tokenizer.eos_token_id, use_bitmask=False, vocab_size=vocab_size)


def prefix_function(tokenizer_data, parser):
    config = parser.config
    enforcer = TokenEnforcer(tokenizer_data, parser)
    # TokenEnforcer derives an alphabet from token starts and replaces the
    # supplied config. Byte fragments can hide Hindi characters such as ।
    # from that alphabet. Preserve the explicit Devanagari alphabet and order.
    parser.config = config

    def allowed(batch_id, token_ids):
        return enforcer.get_allowed_tokens(token_ids.tolist()).allowed_tokens
    return allowed
