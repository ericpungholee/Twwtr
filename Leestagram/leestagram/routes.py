import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from leestagram import app, db, bcrypt
from leestagram.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, CommentForm, SearchForm
from leestagram.models import User, Post, Comment, Like
from flask_login import login_user, current_user, logout_user, login_required


@app.route("/")
@app.route('/home', methods=['POST', 'GET'])
def home():
    form = CommentForm()
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return render_template('home.html', posts=posts, form=form)


@app.route("/about")
def about():
    form = SearchForm()
    return render_template('about.html', title='About', form=form)


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You ar now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    comment = CommentForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    # Get all the posts of the logged in user
    page = request.args.get('page', 1, type=int)
    user=current_user
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return render_template('account.html', title='Account', image_file=image_file, comment=comment, posts=posts, user=user, form=form)



@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post', form=form, legend='New Post')


@app.route("/post/<int:post_id>")
def post(post_id):
    form = CommentForm()
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post, form=form)

@app.route('/post/<int:post_id>/update', methods=["POST", "GET"])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form=PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template("create_post.html", title="Update Post", form=form, legend="Update Post")

@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    
    # Delete comments and likes for the post
    comments = Comment.query.filter_by(post_id=post.id).all()
    likes = Like.query.filter_by(post_id=post.id).all()

    for comment in comments:
        db.session.delete(comment)

    for like in likes:
        db.session.delete(like)

    # Delete the post
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))

@app.route("/user/<string:username>")
def profile(username):
    form = CommentForm()
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page)
    return render_template('profile.html', user=user, posts=posts, form=form, title=f"profile - {username}")


@app.route("/create-comment/<post_id>", methods=['POST'])
@login_required
def create_comment(post_id):
    form = CommentForm()
    if form.validate_on_submit():
        post = Post.query.filter_by(id=post_id).first()
        if post:
            comment = Comment(content=form.content.data, user_id=current_user.id, post_id=post_id, user=current_user)
            db.session.add(comment)
            db.session.commit()
            flash('Comment added successfully.', category='success')
        else:
            flash('Post does not exist.', category='error')
    else:
        flash('Comment cannot be empty.', category='error')
    return redirect(request.referrer)




@app.route("/delete-comment/<comment_id>")
@login_required
def delete_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id).first()
    if not comment:
        flash('comment does not exist.', category='error')
    elif current_user.id != comment.user_id:
        flash('You do not have permission.', category='error')
    else:
        db.session.delete(comment)
        db.session.commit()
    return redirect(request.referrer)

@app.route("/like-post/<post_id>", methods=["GET"])
@login_required
def like(post_id):
    post = Post.query.filter_by(id=post_id).first()
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not post:
        flash('Post does not exist.', category='error')
    elif like:
        db.session.delete(like)
        db.session.commit()
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
    return redirect(request.referrer)


@app.route('/search', methods=['POST'])
def search():
    form = SearchForm()
    users = User.query
    if form.validate_on_submit():
        users = users.filter(User.username.ilike('%' + form.searched.data + '%'))
        searched = form.searched.data
    else:
        flash('No results')
    return render_template("search.html", form=form, users=users, searched=searched)




