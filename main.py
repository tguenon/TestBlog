from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, AdminUserForm
from flask_gravatar import Gravatar
from functools import wraps
from dotenv import dotenv_values
import os
import psycopg2
import sqlalchemy as sa

SQLITEDB = "sqlite:///blog.db"
config = dotenv_values(".env")


app = Flask(__name__)
app.config['SECRET_KEY'] = config['SECRET_KEY']
ckeditor = CKEditor(app)
Bootstrap5(app)
app.config['BOOTSTRAP_ICON_COLOR'] = config['ICON_BASE_COLOR']
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'Yeti'


# CONNECT TO DB
if os.getenv('DATABASE_URL'):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
else:
    SQLALCHEMY_DATABASE_URI = SQLITEDB

# print(SQLALCHEMY_DATABASE_URI)

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy()
db.init_app(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='x',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    # return User.get(user_id)
    a_user = db.session.get(User, int(user_id))
    return a_user


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author = relationship("User", back_populates="posts")
    comments = relationship("Comments", back_populates="posts")


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    admin = db.Column(db.Boolean())
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comments", back_populates="author")


class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="comments")
    posts = relationship("BlogPost", back_populates="comments")


@app.errorhandler(403)
def handle_bad_request(e):
    return render_template('403.html', logged_in=current_user.is_authenticated), 403


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # if not(current_user.get_id()) or int(current_user.get_id()) != 1:
        if not is_admin():
            return abort(403)
            # return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def is_admin():
    admin_user = False
    if current_user.get_id():
        with app.app_context():
            admin_user = db.session.get(User, int(current_user.get_id())).admin
    return admin_user


# Check if the database needs to be initialized
# not for SQLite at it seems that inspector.has_table() fails to return a valid status

if app.config['SQLALCHEMY_DATABASE_URI'] != SQLITEDB:
    # print(app.config['SQLALCHEMY_DATABASE_URI'])
    engine = sa.create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    # print(engine)
    inspector = sa.inspect(engine)
    # print(inspector)
    # print(type(inspector))
    # print(inspector.info_cache)
    # print(inspector.get_schema_names())
    # print(inspector.default_schema_name)
    # print(inspector.get_table_names())
    if not inspector.has_table(table_name="user"):
        # print(inspector.has_table(table_name="user"))
        # print("DB Init")
        with app.app_context():
            db.drop_all()
            db.create_all()
            # adding one admin user so that we're not stuck
            admin_user = User()
            admin_user.email = config['ADMIN_USER']
            # admin_user.password = generate_password_hash(config['ADMIN_PWD'], method='pbkdf2:sha256', salt_length=8)
            admin_user.password = config['ADMIN_HASH_PWD']
            admin_user.name = config['ADMIN_NAME']
            admin_user.admin = True
            with app.app_context():
                db.session.add(admin_user)
                db.session.commit()
            app.logger.info('Initialized the database!')
    else:
        print("DB exist")
        app.logger.info('Database already contains the needed tables.')

with app.app_context():
    posts = db.session.execute(db.select(BlogPost)).scalars().all()


@app.route('/')
def get_all_posts():
    global posts
    with app.app_context():
        posts = db.session.execute(db.select(BlogPost)).scalars().all()
        return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, admin_user=is_admin())


@app.route('/user_list', methods=["GET", "POST"])
@admin_only
def list_users():
    users = db.session.execute(db.select(User).order_by(User.name)).scalars().all()
    #
    # def sort_on_name(e):
    #     return e['name']
    return render_template("user_list.html", user_list=users, logged_in=current_user.is_authenticated, admin_user=is_admin())


@app.route('/update_user/<int:user_id>', methods=["GET", "POST"])
@admin_only
def update_user(user_id):
    user_to_update = db.session.get(User, user_id)
    user_form = AdminUserForm(
        email=user_to_update.email,
        password=user_to_update.password,
        name=user_to_update.name,
        admin_toggle=user_to_update.admin,
    )
    if user_form.validate_on_submit():
        user_to_update.email = user_form.email.data
        # print(user_form.password.data)
        # print(user_to_update.password)
        if user_form.password.data != user_to_update.password:
            user_to_update.password = generate_password_hash(user_form.password.data, method='pbkdf2:sha256', salt_length=8)
        user_to_update.name = user_form.name.data
        user_to_update.admin = user_form.admin_toggle.data
        db.session.commit()
        # print("User update done")
        return redirect(url_for('get_all_posts'))
    return render_template("edit-user.html", form=user_form, logged_in=current_user.is_authenticated, admin_user=is_admin())


@app.route('/register', methods=["GET", "POST"])
def register():
    new_user = RegisterForm(request.form)
    if request.method == "POST" and new_user.validate():
        existing_user = db.session.execute(db.select(User).where(User.email == new_user.email.data))
        existing_user_lst = existing_user.all()
        test = len(existing_user_lst)
        if test == 0:
            user_in_db = User()
            user_in_db.email = new_user.email.data
            user_in_db.password = generate_password_hash(new_user.password.data, method='pbkdf2:sha256', salt_length=8)
            user_in_db.name = new_user.name.data
            with app.app_context():
                db.session.add(user_in_db)
                db.session.commit()
                login_user(user_in_db)
            return redirect(url_for('get_all_posts'))
        else:
            flash("Sorry, a user with this password already exist. Log in instead")
            return redirect(url_for('login'))
    return render_template("register.html", form=new_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    a_user = LoginForm(request.form)
    if request.method == "POST" and a_user.validate():
        blog_user = db.session.execute(db.select(User).where(User.email == a_user.email.data))
        blog_user_lst = blog_user.all()
        test = len(blog_user_lst)
        if test != 0:
            blog_user = db.session.execute(db.select(User).where(User.email == a_user.email.data)).scalar_one()
            if check_password_hash(blog_user.password, a_user.password.data):
                login_user(blog_user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Sorry, wrong password")
                return redirect(url_for('login'))
        else:
            flash("user email doesn't exist")
            return redirect(url_for('login'))
    return render_template("login.html", form=a_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    new_comment = CommentForm(request.form)

    requested_post = db.session.get(BlogPost, post_id)

    if request.method == "POST" and new_comment.validate():
        comment_in_db = Comments()
        comment_in_db.text = new_comment.body.data
        comment_in_db.author_id = int(current_user.get_id())
        comment_in_db.post_id = post_id
        with app.app_context():
            db.session.add(comment_in_db)
            db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))

    return render_template("post.html", form=new_comment, post=requested_post, comments=requested_post.comments,
                           logged_in=current_user.is_authenticated, admin_user=is_admin())


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=int(current_user.get_id()),
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated, is_edit=False)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.session.get(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.session.get(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
