import logging
from unittest.mock import patch, call, MagicMock

import listenbrainz_spark
from listenbrainz_spark.recommendations.recording.tests import RecommendationsTestCase
from listenbrainz_spark.recommendations.recording import recommend
from listenbrainz_spark import schema, utils, path
from listenbrainz_spark.exceptions import (RecommendationsNotGeneratedException,
                                           EmptyDataframeExcpetion)

from pyspark.sql import Row
from pyspark.rdd import RDD
from pyspark.sql.functions import col

# for test data/dataframes refer to listenbrainzspark/tests/__init__.py

logger = logging.getLogger(__name__)


class RecommendTestClass(RecommendationsTestCase):

    def test_recommendation_params_init(self):
        recordings_df = utils.create_dataframe(Row(col1=3, col2=9), schema=None)
        model = MagicMock()
        top_artist_candidate_set_df = utils.create_dataframe(Row(col1=4, col2=5, col3=5), schema=None)
        similar_artist_candidate_set_df = utils.create_dataframe(Row(col1=1), schema=None)
        recommendation_top_artist_limit = 20
        recommendation_similar_artist_limit = 40

        params = recommend.RecommendationParams(recordings_df, model, top_artist_candidate_set_df,
                                                similar_artist_candidate_set_df,
                                                recommendation_top_artist_limit,
                                                recommendation_similar_artist_limit)

        self.assertEqual(sorted(params.recordings_df.columns), sorted(recordings_df.columns))
        self.assertEqual(params.model, model)
        self.assertEqual(sorted(params.top_artist_candidate_set_df.columns), sorted(top_artist_candidate_set_df.columns))
        self.assertEqual(sorted(params.similar_artist_candidate_set_df.columns), sorted(similar_artist_candidate_set_df.columns))
        self.assertEqual(params.recommendation_top_artist_limit, recommendation_top_artist_limit)
        self.assertEqual(params.recommendation_similar_artist_limit, recommendation_similar_artist_limit)

    def get_recordings_df(self):
        return listenbrainz_spark.session.createDataFrame([
            Row(artist_credit_id=1, recording_mbid="3acb406f-c716-45f8-a8bd-96ca3939c2e5", recording_id=1),
            Row(artist_credit_id=2, recording_mbid="2acb406f-c716-45f8-a8bd-96ca3939c2e5", recording_id=2)
        ])

    def get_recommendation_df(self):
        return listenbrainz_spark.session.createDataFrame([
            Row(spark_user_id=1, recording_id=1, rating=0.313456),
            Row(spark_user_id=1, recording_id=2, rating=6.994590001),
            Row(spark_user_id=2, recording_id=2, rating=-2.4587),
            Row(spark_user_id=2, recording_id=1, rating=7.999)
        ])

    def test_get_recording_mbids(self):
        params = self.get_recommendation_params()
        recommendation_df = self.get_recommendation_df()
        users = []
        users_df = recommend.get_user_name_and_user_id(params, users)

        df = recommend.get_recording_mbids(params, recommendation_df, users_df)
        self.assertEqual(df.count(), 4)
        # Each user's rows are ordered by ratings but the order of users is not
        # fixed so need to test each user's recommendations separately.
        rows_rob = df.where(df.user_id == 1).collect()
        self.assertEqual(rows_rob, [
            Row(
                recording_mbid="3acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rank=1,
                rating=7.999,
                spark_user_id=2,
                user_id=1
            ),
            Row(
                recording_mbid="2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rank=2,
                rating=-2.4587,
                spark_user_id=2,
                user_id=1
            )
        ])
        rows_vansika = df.where(df.user_id == 3).collect()
        self.assertEqual(rows_vansika, [
            Row(recording_mbid="2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rank=1,
                rating=6.994590001,
                spark_user_id=1,
                user_id=3),
            Row(
                recording_mbid="3acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rank=2,
                rating=0.313456,
                spark_user_id=1,
                user_id=3
                ),
        ])

    def test_filter_recommendations_on_rating(self):
        df = self.get_recommendation_df()
        recommendation_df = df.select(col('spark_user_id').alias('user'),
                                      col('recording_id').alias('product'),
                                      col('rating'))
        limit = 1

        df = recommend.filter_recommendations_on_rating(recommendation_df, limit)
        self.assertEqual(df.count(), 2)
        row = df.collect()

        received_data = [row[0], row[1]]
        expected_data = [
            Row(
                rating=6.994590001,
                recording_id=2,
                spark_user_id=1),
            Row(
                rating=7.999,
                recording_id=1,
                spark_user_id=2)
        ]

        self.assertEqual(received_data, expected_data)

    @patch('listenbrainz_spark.recommendations.recording.recommend.filter_recommendations_on_rating')
    @patch('listenbrainz_spark.recommendations.recording.recommend.listenbrainz_spark')
    def test_generate_recommendations(self, mock_lb, mock_filter):
        params = self.get_recommendation_params()
        limit = 1

        mock_model = MagicMock()
        params.model = mock_model

        mock_predict = mock_model.predictAll
        candidate_set = self.get_candidate_set()
        users = []

        rdd = recommend.get_candidate_set_rdd_for_user(candidate_set, users)
        mock_predict.return_value = rdd

        df = recommend.generate_recommendations(candidate_set, params, limit)

        mock_predict.assert_called_once_with(candidate_set)

        mock_df = mock_lb.session.createDataFrame
        mock_df.assert_called_once_with(mock_predict.return_value, schema=None)

        mock_filter.assert_called_once_with(mock_df.return_value, limit)

        with self.assertRaises(RecommendationsNotGeneratedException):
            # empty rdd
            mock_predict.return_value = MagicMock()
            recommend.generate_recommendations(candidate_set, params, limit)

    def test_get_scale_rating_udf(self):
        rating = 1.6
        res = recommend.get_scale_rating_udf(rating)
        self.assertEqual(res, 1.0)

        rating = -1.6
        res = recommend.get_scale_rating_udf(rating)
        self.assertEqual(res, -0.3)

        rating = 0.65579
        res = recommend.get_scale_rating_udf(rating)
        self.assertEqual(res, 0.828)

        rating = -0.9999
        res = recommend.get_scale_rating_udf(rating)
        self.assertEqual(res, 0.0)

    def test_scale_rating(self):
        df = self.get_recommendation_df()

        df = recommend.scale_rating(df)
        self.assertEqual(sorted(df.columns), ['rating', 'recording_id', 'spark_user_id'])
        received_ratings = sorted([row.rating for row in df.collect()])
        expected_ratings = [-0.729, 0.657, 1.0, 1.0]

    def test_get_candidate_set_rdd_for_user(self):
        candidate_set = self.get_candidate_set()
        users = []

        candidate_set_rdd = recommend.get_candidate_set_rdd_for_user(candidate_set, users)
        self.assertTrue(isinstance(candidate_set_rdd, RDD))
        res = sorted([row for row in candidate_set_rdd.collect()])
        self.assertEqual(res, [(1, 1), (2, 2)])

        users = [3]
        candidate_set_rdd = recommend.get_candidate_set_rdd_for_user(candidate_set, users)

        self.assertTrue(isinstance(candidate_set_rdd, RDD))
        row = candidate_set_rdd.collect()
        self.assertEqual([(1, 1)], row)

        users = [4]
        with self.assertRaises(EmptyDataframeExcpetion):
            recommend.get_candidate_set_rdd_for_user(candidate_set, users)

    def test_get_user_name_and_user_id(self):
        params = self.get_recommendation_params()
        df = utils.create_dataframe(
            Row(
                spark_user_id=1,
                user_id=3,
                recording_id=1
            ),
            schema=None
        )

        df = df.union(utils.create_dataframe(
            Row(
                spark_user_id=1,
                user_id=3,
                recording_id=2
            ),
            schema=None
        ))

        df = df.union(utils.create_dataframe(
            Row(
                spark_user_id=2,
                user_id=1,
                recording_id=1
            ),
            schema=None
        ))

        params.top_artist_candidate_set_df = df

        users = []
        users_df = recommend.get_user_name_and_user_id(params, [])

        self.assertEqual(users_df.count(), 2)
        user_id = sorted([row.user_id for row in users_df.collect()])
        spark_user_id = sorted([row.spark_user_id for row in users_df.collect()])
        self.assertEqual(sorted(users_df.columns), sorted(['spark_user_id', 'user_id']))
        self.assertEqual([1, 3], user_id)
        self.assertEqual([1, 2], spark_user_id)

        users = [3, 100]
        users_df = recommend.get_user_name_and_user_id(params, users)
        self.assertEqual(users_df.count(), 1)
        self.assertEqual(sorted(users_df.columns), sorted(['spark_user_id', 'user_id']))
        user_id = [row.user_id for row in users_df.collect()]
        spark_user_id = [row.spark_user_id for row in users_df.collect()]
        self.assertEqual([3], user_id)
        self.assertEqual([1], spark_user_id)

        with self.assertRaises(EmptyDataframeExcpetion):
            users = ['invalid']
            recommend.get_user_name_and_user_id(params, users)

    @patch('listenbrainz_spark.recommendations.recording.recommend.MatrixFactorizationModel')
    @patch('listenbrainz_spark.recommendations.recording.recommend.listenbrainz_spark')
    @patch('listenbrainz_spark.recommendations.recording.recommend.get_model_path')
    @patch('listenbrainz_spark.recommendations.recording.recommend.get_most_recent_model_id')
    def test_load_model(self, mock_id, mock_model_path, mock_lb, mock_matrix_model):
        model = recommend.load_model()
        mock_id.assert_called_once()
        mock_model_path.assert_called_once_with(mock_id.return_value)
        mock_matrix_model.load.assert_called_once_with(mock_lb.context, mock_model_path.return_value)

    def test_get_most_recent_model_id(self):
        model_id_1 = "a36d6fc9-49d0-4789-a7dd-a2b72369ca45"
        model_metadata_dict_1 = self.get_model_metadata(model_id_1)
        df_1 = utils.create_dataframe(schema.convert_model_metadata_to_row(model_metadata_dict_1),
                                      schema.model_metadata_schema)

        model_id_2 = "bbbd6fc9-49d0-4789-a7dd-a2b72369ca45"
        model_metadata_dict_2 = self.get_model_metadata(model_id_2)
        df_2 = utils.create_dataframe(schema.convert_model_metadata_to_row(model_metadata_dict_2),
                                      schema.model_metadata_schema)

        model_metadata = df_1.union(df_2)
        utils.save_parquet(model_metadata, path.RECOMMENDATION_RECORDING_MODEL_METADATA)

        expected_model_id = recommend.get_most_recent_model_id()
        self.assertEqual(expected_model_id, model_id_2)

    @patch('listenbrainz_spark.recommendations.recording.recommend.get_candidate_set_rdd_for_user')
    @patch('listenbrainz_spark.recommendations.recording.recommend.generate_recommendations')
    def test_get_recommendations_for_all(self, mock_recs, mock_candidate_set):
        params = self.get_recommendation_params()
        users = [3]

        params.top_artist_candidate_set_df = self.get_top_artist_rec_df()
        params.similar_artist_candidate_set_df = self.get_similar_artist_rec_df()

        def side_effect(df, users):

            if len(df.subtract(params.top_artist_candidate_set_df).collect()) == 0:
                return 'top_artist_rdd'

            if len(df.subtract(params.similar_artist_candidate_set_df).collect()) == 0:
                return 'similar_artist_rdd'

        mock_candidate_set.side_effect = side_effect

        recommend.get_recommendations_for_all(params, users)

        mock_candidate_set.assert_has_calls([
            call(params.top_artist_candidate_set_df, users),
            call(params.similar_artist_candidate_set_df, users)
        ])

        mock_recs.assert_has_calls([
            call(mock_candidate_set(params.top_artist_candidate_set_df, users), params, params.recommendation_top_artist_limit),
            call(mock_candidate_set(params.similar_artist_candidate_set_df, users), params, params.recommendation_similar_artist_limit)
        ])

    def get_top_artist_rec_df(self):
        df = utils.create_dataframe(
            Row(recording_mbid="2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=1.8,
                recording_id=5,
                spark_user_id=6,
                user_id=3),
            schema=None
        )

        df = df.union(utils.create_dataframe(
            Row(recording_mbid="8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=-0.8,
                recording_id=6,
                spark_user_id=6,
                user_id=3),
            schema=None
        ))

        df = df.union(utils.create_dataframe(
            Row(recording_mbid="8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=0.99,
                recording_id=6,
                spark_user_id=7,
                user_id=1),
            schema=None
        ))
        return df

    def get_similar_artist_rec_df(self):
        df = utils.create_dataframe(
            Row(recording_mbid="2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=0.8,
                recording_id=5,
                spark_user_id=8,
                user_id=4),
            schema=None
        )

        df = df.union(utils.create_dataframe(
            Row(recording_mbid="8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=-2.8,
                recording_id=6,
                spark_user_id=8,
                user_id=4),
            schema=None
        ))

        df = df.union(utils.create_dataframe(
            Row(recording_mbid="7acb406f-c716-45f8-a8bd-96ca3939c2e5",
                rating=0.19,
                recording_id=11,
                spark_user_id=7,
                user_id=1),
            schema=None
        ))
        return df

    def test_check_for_ratings_beyond_range(self):
        top_artist_rec_df = self.get_top_artist_rec_df()
        similar_artist_rec_df = self.get_similar_artist_rec_df()

        min_test, max_test = recommend.check_for_ratings_beyond_range(top_artist_rec_df, similar_artist_rec_df)
        self.assertEqual(min_test, True)
        self.assertEqual(max_test, True)

    def test_create_messages(self):
        top_artist_rec_df = self.get_top_artist_rec_df()
        similar_artist_rec_df = self.get_similar_artist_rec_df()
        active_user_count = 10
        top_artist_rec_user_count = 5
        similar_artist_rec_user_count = 4
        total_time = 3600

        data = recommend.create_messages(top_artist_rec_df, similar_artist_rec_df, active_user_count, total_time,
                               top_artist_rec_user_count, similar_artist_rec_user_count)

        self.assertEqual(next(data), {
            'user_id': 3,
            'type': 'cf_recommendations_recording_recommendations',
            'recommendations': {
                'top_artist': [
                    {
                        'recording_mbid': "2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': 1.8
                    },
                    {
                        'recording_mbid': "8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': -0.8
                    }
                ],
                'similar_artist': []
            }
        })

        self.assertEqual(next(data), {
            'user_id': 1,
            'type': 'cf_recommendations_recording_recommendations',
            'recommendations': {
                'top_artist': [
                    {
                        'recording_mbid': "8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': 0.99
                    }
                ],
                'similar_artist': [
                    {
                        'recording_mbid': "7acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': 0.19
                    }
                ]
            }
        })

        self.assertEqual(next(data), {
            'user_id': 4,
            'type': 'cf_recommendations_recording_recommendations',
            'recommendations': {
                'top_artist': [],
                'similar_artist': [
                    {
                        'recording_mbid': "2acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': 0.8
                    },
                    {
                        'recording_mbid': "8acb406f-c716-45f8-a8bd-96ca3939c2e5",
                        'score': -2.8
                    }
                ]
            }
        })

        self.assertEqual(next(data), {
            'type': 'cf_recommendations_recording_mail',
            'active_user_count': active_user_count,
            'top_artist_user_count': top_artist_rec_user_count,
            'similar_artist_user_count': similar_artist_rec_user_count,
            'total_time': '1.00'
        })

    def test_get_user_count(self):
        df = utils.create_dataframe(Row(spark_user_id=3), schema=None)
        df = df.union(utils.create_dataframe(Row(spark_user_id=3), schema=None))
        df = df.union(utils.create_dataframe(Row(spark_user_id=2), schema=None))

        user_count = recommend.get_user_count(df)
        self.assertEqual(user_count, 2)

    def get_recommendation_params(self):
        recordings_df = self.get_recordings_df()
        model = MagicMock()
        top_artist_candidate_set_df = self.get_candidate_set()
        similar_artist_candidate_set_df = self.get_candidate_set()
        recommendation_top_artist_limit = 2
        recommendation_similar_artist_limit = 1

        params = recommend.RecommendationParams(recordings_df, model, top_artist_candidate_set_df,
                                                similar_artist_candidate_set_df,
                                                recommendation_top_artist_limit,
                                                recommendation_similar_artist_limit)
        return params
