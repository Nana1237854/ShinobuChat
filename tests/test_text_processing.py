import unittest

from app.services.emotion_parser import parse_emotion_tag, resolve_emotion, strip_leading_control_blocks
from app.services.sentence_splitter import split_long_sentence, split_sentences
from app.services.text_cleaner import clean_tts_text, strip_tts_punctuation


class TextCleanerTests(unittest.TestCase):
    def test_clean_tts_text_removes_markup_tags_and_emoji(self):
        self.assertEqual(
            clean_tts_text("[happy] **你好**（悄悄说） → `世界` 😊！！"),
            "你好世界！",
        )

    def test_clean_tts_text_strips_markdown_tables_and_spaces(self):
        text = "# 标题\n- 第一 项\n| A | B |\n|---|---|\n"
        self.assertEqual(clean_tts_text(text), "标题第一项")

    def test_strip_tts_punctuation_keeps_words_for_speech(self):
        self.assertEqual(
            strip_tts_punctuation("听到你心情不好，我也觉得有点难过……"),
            "听到你心情不好我也觉得有点难过",
        )


class SentenceSplitterTests(unittest.TestCase):
    def test_split_sentences_returns_finished_sentences_and_remaining_text(self):
        sentences, remaining = split_sentences("你好呀。今天还好吗？我在想")

        self.assertEqual(sentences, ["你好呀。", "今天还好吗？"])
        self.assertEqual(remaining, "我在想")

    def test_split_long_sentence_uses_commas_when_over_limit(self):
        result = split_long_sentence("第一段很长很长很长，第二段也很长很长很长，第三段收尾", max_len=12)

        self.assertEqual(result, ["第一段很长很长很长", "第二段也很长很长很长", "第三段收尾"])


class EmotionParserTests(unittest.TestCase):
    def test_parse_emotion_tag_extracts_leading_tag(self):
        emotion, text = parse_emotion_tag("[emotion: happy] 见到你真好")

        self.assertEqual(emotion, "happy")
        self.assertEqual(text, "见到你真好")

    def test_parse_emotion_tag_hides_leading_thinking_block(self):
        emotion, text = parse_emotion_tag(
            "[thinking]内部推理，不展示[/thinking]\n\n[sad]我会好好听你说。"
        )

        self.assertEqual(emotion, "sad")
        self.assertEqual(text, "我会好好听你说。")

    def test_strip_leading_control_blocks_keeps_normal_thinking_emotion(self):
        self.assertEqual(
            strip_leading_control_blocks("[thinking]我在想这个问题。"),
            "[thinking]我在想这个问题。",
        )

    def test_resolve_emotion_falls_back_to_neutral(self):
        self.assertEqual(resolve_emotion(None), "neutral")
        self.assertEqual(resolve_emotion("unknown"), "neutral")


if __name__ == "__main__":
    unittest.main()
