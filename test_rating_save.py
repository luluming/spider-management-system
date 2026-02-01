from django.test import TestCase
from django.utils import timezone
from spiders.models import PSentiment


class RatingSaveTests(TestCase):
    """Tests for rating formatting and saving behavior."""

    def format_rating(self, comment_num):
        try:
            comment_num_float = float(comment_num) if comment_num else 0.0
            comment_num_str = f"{round(comment_num_float, 1):.1f}"
            return comment_num_str
        except ValueError:
            return None

    def test_format_and_save(self):
        test_cases = [
            ('test_rating_1', '4.8', '应该保存为4.8'),
            ('test_rating_2', '4.75', '应该保存为4.8（四舍五入）'),
            ('test_rating_3', '5', '应该保存为5.0'),
            ('test_rating_4', '4.99', '应该保存为5.0（四舍五入）'),
        ]

        for poi_id, input_val, desc in test_cases:
            formatted = self.format_rating(input_val)

            # ensure no pre-existing record
            PSentiment.objects.filter(poiId=poi_id).delete()

            # create and verify
            rec = PSentiment.objects.create(
                poiId=poi_id,
                comment_num=formatted,
                reply_num=100,
                p_time=timezone.now()
            )

            saved_record = PSentiment.objects.get(poiId=poi_id)
            self.assertEqual(str(saved_record.comment_num), formatted)

            # cleanup
            PSentiment.objects.filter(poiId=poi_id).delete()



