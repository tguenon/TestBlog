from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.widgets import PasswordInput
from wtforms.validators import DataRequired, InputRequired, URL, Email
from flask_ckeditor import CKEditorField


##WTForm


class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField("Blog Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    name = StringField("Name", validators=[InputRequired()])
    submit = SubmitField("Sign me up!")


class AdminUserForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email()])
    password = StringField("Password", widget=PasswordInput(hide_value=False))
    name = StringField("Name", validators=[InputRequired()])
    admin_toggle = BooleanField("Administrator", false_values=(False,"false"))
    submit = SubmitField("Update")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Let me in!")


class CommentForm(FlaskForm):
    body = CKEditorField("Your comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment")