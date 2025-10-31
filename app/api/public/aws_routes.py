from flask import jsonify
import boto3
import botocore
from config import config
import os
import logging

logger = logging.getLogger(__name__)

env = os.environ.get('FLASK_ENV', 'development')
app_config = config.get(env, config['default'])

try:
    s3 = boto3.client('s3',
                      aws_access_key_id=app_config.AWS_ACCESS_KEY_ID,
                      aws_secret_access_key=app_config.AWS_SECRET_ACCESS_KEY,
                      region_name=app_config.AWS_REGION,
                      endpoint_url=app_config.AWS_ENDPOINT,
                      config=botocore.client.Config(signature_version='s3v4'))
except Exception as e:
    logger.error(f"Failed to initialize S3 client: {e}")
    s3 = None

def init_aws_routes(app):
    @app.route('/img_keys', methods=['GET'])
    def get_img_keys():
        """Получить ключи для загрузки изображений в S3"""
        try:
            if not s3:
                return jsonify({'error': 'S3 service not available'}), 500

            key = 'users/uploads/${filename}'
            bucket = 'team2go'
            conditions = [{"acl": "public-read"}, ["starts-with", "$key", "users/uploads"]]
            fields = {'success_action_redirect': ''}

            prepared_form_fields = s3.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Conditions=conditions,
                Fields=fields,
                ExpiresIn=60 * 60
            )

            logger.info("Generated presigned post for image upload")
            return jsonify(prepared_form_fields), 200

        except Exception as e:
            logger.error(f"Error generating presigned post: {e}")
            return jsonify({'error': 'Failed to generate upload credentials'}), 500

