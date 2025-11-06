from flask import Flask, session
from flask_cors import CORS
from flasgger import Swagger
from flask_swagger_ui import get_swaggerui_blueprint
from app.api.public import (auth_routes, post_routes, user_routes, like_routes, comment_routes, rating_routes,
                            activities_routes, aws_routes, password_routes, challenges_api_routes)
from app.api.admin import admin_users_routes, admin_common_routes, admin_moderation_routes, admin_teams_routes, admin_challenges_api_routes
from admin_scripts import create_teams, recalc_points, import_db, create_leagues
from config import config
import os
import boto3
import botocore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    env = os.environ.get('FLASK_ENV', 'development')
    app_config = config.get(env, config['default'])
    app.config.from_object(app_config)
    CORS(app, supports_credentials=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    SWAGGER_URL = '/apidocs'
    API_URL = '/static/swagger.yaml'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={'app_name': "Sport App API"}
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
    return app

app = create_app()

auth_routes.init_auth_routes(app)
post_routes.init_post_routes(app)
user_routes.init_user_routes(app)
like_routes.init_like_routes(app)
comment_routes.init_comment_routes(app)
rating_routes.init_rating_routes(app)
activities_routes.init_activities_routes(app)
aws_routes.init_aws_routes(app)
password_routes.init_password_routes(app)
challenges_api_routes.init_challenges_api_routes(app)
admin_users_routes.init_admin_users_routes(app)
admin_common_routes.init_admin_common_routes(app)
admin_moderation_routes.init_admin_moderation_routes(app)
admin_teams_routes.init_admin_teams_routes(app)
admin_challenges_api_routes.init_admin_challenges_api_routes(app)

# create_leagues.create_leagues()
# create_teams.create_teams()
# recalc_points.recalculate_all_users_points()
# import_db.import_csv_to_users_table('C:/Users/User/PycharmProjects/sport_auth/admin/test_users.csv')

if __name__ == '__main__':
    app.run(debug=True)