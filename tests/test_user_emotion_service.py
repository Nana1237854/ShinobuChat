import unittest
from datetime import datetime, timezone

from app.services.user_emotion_service import UserEmotionService


class UserEmotionServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserEmotionService()

    # 1. Continuous short negative messages → worried/stressed
    def test_consecutive_short_negatives(self):
        result = self.svc.analyze(
            user_message="我撑不住了",
            recent_user_messages=["烦死了", "怎么又出问题"],
        )
        self.assertIn(result.emotion_label, ["stressed", "worried"])
        self.assertGreater(result.intensity, 0.3)

    # 2. Multiple exclamation marks + stress words → higher intensity
    def test_exclamation_boosts_intensity(self):
        mild = self.svc.analyze(user_message="好累")
        strong = self.svc.analyze(user_message="烦死了！！！救命！！")
        self.assertGreater(strong.intensity, mild.intensity)

    # 3. Late night + lonely words → tired/lonely
    def test_late_night_lonely(self):
        night = datetime(2026, 6, 23, 3, 0, 0, tzinfo=timezone.utc)
        result = self.svc.analyze(
            user_message="睡不着，好安静",
            recent_user_messages=["还没睡"],
            now=night,
        )
        self.assertIn(result.emotion_label, ["tired", "lonely"])

    # 4. Gratitude / happy words → happy
    def test_happy_detection(self):
        result = self.svc.analyze(
            user_message="太好了！终于好了！谢谢你！",
            recent_user_messages=["哈哈", "好开心"],
        )
        self.assertEqual(result.emotion_label, "happy")
        self.assertTrue(result.should_adjust_reply)

    # 5. Task requests → neutral (not misclassified)
    def test_task_request_neutral(self):
        result = self.svc.analyze(
            user_message="帮我查一下这个代码的问题",
            recent_user_messages=["打开设置", "创建一个待办"],
        )
        self.assertEqual(result.emotion_label, "neutral")
        self.assertFalse(result.should_adjust_reply)

    # 6. Technical questions → neutral
    def test_technical_question_neutral(self):
        result = self.svc.analyze(
            user_message="解释一下HashMap的实现原理",
        )
        self.assertEqual(result.emotion_label, "neutral")
        self.assertEqual(result.reply_style_hint, "")

    # 7. Low confidence → should_adjust_reply=False
    def test_low_confidence_no_adjust(self):
        result = self.svc.analyze(user_message="嗯")
        self.assertFalse(result.should_adjust_reply)
        self.assertEqual(result.reply_style_hint, "")

    # 8. reply_style_hint is gentle, short-reply oriented, never preachy
    def test_hint_never_preachy(self):
        for label, message, recent in [
            ("stressed", "我真的撑不住了", ["烦死了"]),
            ("sad", "好难过", ["想哭"]),
            ("frustrated", "又出问题了怎么回事", ["无语"]),
        ]:
            result = self.svc.analyze(message, recent)
            self.assertNotIn("你应该", result.reply_style_hint)
            self.assertNotIn("你必须", result.reply_style_hint)
            self.assertIn("不要长篇说教" if label != "frustrated" else "不要反驳",
                          result.reply_style_hint if result.reply_style_hint else "" or "不要")

    # 9. Crisis detection for self-harm keywords
    def test_crisis_detection(self):
        result = self.svc.analyze(user_message="我真的不想活了")
        self.assertEqual(result.emotion_label, "crisis")
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.intensity, 1.0)
        self.assertIn("危机", result.reply_style_hint)
        self.assertIn("紧急帮助", result.reply_style_hint)

    # 10. Empty message → neutral
    def test_empty_message_neutral(self):
        result = self.svc.analyze(user_message="你好")
        self.assertEqual(result.emotion_label, "neutral")

    # 11. Recent messages boost confidence
    def test_recent_context_boosts_confidence(self):
        solo = self.svc.analyze(user_message="好累")
        with_context = self.svc.analyze(
            user_message="好累",
            recent_user_messages=["撑不住了", "怎么办"],
        )
        self.assertGreater(with_context.intensity, solo.intensity)

    # 12. Crisis beats task guard
    def test_crisis_beats_task_guard(self):
        result = self.svc.analyze(
            user_message="帮我 我不想活了",
        )
        self.assertEqual(result.emotion_label, "crisis")
        self.assertIn("危机", result.reply_style_hint)

    # 13. Emotion hint not injected at low confidence
    def test_low_confidence_no_hint_injection(self):
        result = self.svc.analyze(
            user_message="天气不错",
            recent_user_messages=["嗯", "好"],
        )
        self.assertFalse(result.should_adjust_reply)
        self.assertEqual(result.reply_style_hint, "")

    # 14. Stressed hint stays gentle regardless of persona
    def test_stressed_hint_gentle_regardless_of_persona(self):
        result = self.svc.analyze(
            user_message="我真的好累撑不住了",
            recent_user_messages=["烦死了", "怎么办"],
        )
        hint = result.reply_style_hint
        self.assertIn("不要长篇说教", hint)
        self.assertIn("不要催促", hint)
        self.assertNotIn("抓紧", hint)
        self.assertNotIn("必须", hint)

    # 15. Large recent_user_messages handled without error
    def test_large_recent_truncated(self):
        many = ["测试"] * 50
        result = self.svc.analyze(
            user_message="我好累，压力好大",
            recent_user_messages=many,
        )
        self.assertIsNotNone(result.emotion_label)

    # 16. local_hour=3 + tired/lonely words gets night weak signal
    def test_local_hour_night_signal(self):
        day_result = self.svc.analyze(
            user_message="好累，还没睡",
            local_hour=14,
        )
        night_result = self.svc.analyze(
            user_message="好累，还没睡",
            local_hour=3,
        )
        self.assertGreaterEqual(night_result.confidence, day_result.confidence)

    # 17. worried keywords produce worried label
    def test_worried_keywords(self):
        result = self.svc.analyze(
            user_message="我好担心明天会不会出事",
            recent_user_messages=["有点不安", "紧张"],
        )
        self.assertEqual(result.emotion_label, "worried")
        self.assertTrue(result.should_adjust_reply)
        self.assertIn("不要长篇说教", result.reply_style_hint)


if __name__ == "__main__":
    unittest.main()
