from flask import Flask
from extensions import db, login_manager
from flask_migrate import Migrate

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Initialize Flask-Migrate
    migrate = Migrate(app, db)
    
    with app.app_context():
        from auth import auth_bp
        from routes import main_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        
        db.create_all()
        
    return app

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
