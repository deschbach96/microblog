from datetime import datetime, timezone
from flask import abort, render_template, flash, redirect, url_for, request,jsonify, g, \
    current_app
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
# from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm, \
    MessageForm,CommentForm
from app.models import User, Post, Message, Notification,Comment
from app.translate import translate
from app.main import bp


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())



@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    comment_form = CommentForm() 
    if form.validate_on_submit():
        #  try:
        #     language = detect(form.post.data)
        # except LangDetectException:
        #     language = ''
        try:
            language = form.post.data
        except:
            language = ''
        post = Post(body=form.post.data, author=current_user, language=language)
        db.session.add(post)
        db.session.commit()
        flash(_('Your post is now live!'))
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    
    # Ensure each post includes its associated comments
    for post in posts.items:
        post.comments = Comment.query.filter_by(post_id=post.id, parent_id=None).order_by(Comment.timestamp.asc()).all()
        for comment in post.comments:
            comment.replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.timestamp.asc()).all()
    
    next_url = url_for('main.index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) if posts.has_prev else None
    
    return render_template('index.html', title=_('Home'), form=form,
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url, comment_form=comment_form)



@bp.route('/explore')
@login_required
def explore():
    comment_form = CommentForm() 

    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
        # Ensure each post includes its associated comments
    for post in posts.items:
        post.comments = Comment.query.filter_by(post_id=post.id, parent_id=None).order_by(Comment.timestamp.asc()).all()
        for comment in post.comments:
            comment.replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.timestamp.asc()).all()


    next_url = url_for('main.explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title=_('Explore'),
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url,comment_form=comment_form)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    for post in posts.items:
        post.comments = Comment.query.filter_by(post_id=post.id, parent_id=None).order_by(Comment.timestamp.asc()).all()
        for comment in post.comments:
            comment.replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.timestamp.asc()).all()
    next_url = url_for('main.user', username=user.username,
                       page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username,
                       page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()
    comment_form = CommentForm()
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form,comment_form=comment_form)


@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    form = EmptyForm()
    return render_template('user_popup.html', user=user, form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title=_('Edit Profile'),
                           form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot follow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(_('You are following %(username)s!', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot unfollow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(_('You are not following %(username)s.', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    return {'text': translate(data['text'],
                              data['source_language'],
                              data['dest_language'])}


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title=_('Search'), posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
@login_required
def send_message(recipient):
    user = db.first_or_404(sa.select(User).where(User.username == recipient))
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user,
                      body=form.message.data)
        db.session.add(msg)
        user.add_notification('unread_message_count',
                              user.unread_message_count())
        db.session.commit()
        flash(_('Your message has been sent.'))
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title=_('Send Message'),
                           form=form, recipient=recipient)


@bp.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    query = current_user.messages_received.select().order_by(
        Message.timestamp.desc())
    messages = db.paginate(query, page=page,
                           per_page=current_app.config['POSTS_PER_PAGE'],
                           error_out=False)
    next_url = url_for('main.messages', page=messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) \
        if messages.has_prev else None
    return render_template('messages.html', messages=messages.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_task_in_progress('export_posts'):
        flash(_('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    query = current_user.notifications.select().where(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    notifications = db.session.scalars(query)
    return [{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications]



# comments


@bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment(post_id):
    form = CommentForm()
    print(form.comment.data,"comment")
    post = Post.query.get_or_404(post_id)
    print(post.id, post.body, post.author.username, post.language,)
    if form.validate_on_submit():
        comment = Comment(
            body=form.comment.data,
            author_name=current_user.username,
            post_id=post.id,
            user_id=current_user.id
        )
        db.session.add(comment)
        db.session.commit()
        if request.is_json:
            return jsonify({'message': 'Your comment has been added', 'comment': comment.body}), 201
        flash(_('Your comment has been added.'))
        return redirect(url_for('main.index'))
    if request.is_json:
        return jsonify({'error': 'Invalid form data'}), 400
    flash(_('Failed to add comment.'))
    return redirect(url_for('main.index'))

@bp.route('/edit_comment/<int:comment_id>', methods=['GET', 'POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        abort(403)
    
    form = CommentForm()
    if form.validate_on_submit():
        comment.body = form.comment.data
        db.session.commit()
        if request.is_json:
            return jsonify({'message': 'Your comment has been updated', 'comment': comment.body}), 200
        flash(_('Your comment has been updated.'))
        return redirect(url_for('main.index'))
    elif request.method == 'GET':
        form.comment.data = comment.body
    
    if request.is_json:
        return jsonify({'error': 'Invalid form data'}), 400
    return render_template('edit_comment.html', form=form)

@bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    replies = Comment.query.filter_by(parent_id=comment.id).all()
    if comment.user_id != current_user.id:
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        abort(403)
    
    for reply in replies:
        db.session.delete(reply)
    db.session.delete(comment)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'message': 'Your comment and replies have been deleted'}), 200
    flash(_('Your comment has been deleted.'))
    return redirect(url_for('main.index'))

@bp.route('/reply/<int:comment_id>', methods=['POST'])
@login_required
def reply(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id
    form = CommentForm()
    if form.validate_on_submit():
        reply = Comment(
            body=form.comment.data,
            author_name=current_user.username,
            parent_name=comment.author_name,
            user_id=current_user.id,
            post_id=post_id,
            parent_id=comment.id
        )
        db.session.add(reply)
        db.session.commit()
        if request.is_json:
            return jsonify({'message': 'Your reply has been posted', 'reply': reply.body}), 201
        flash(_('Your reply has been posted.'))
        return redirect(url_for('main.index'))
    
    if request.is_json:
        return jsonify({'error': 'Invalid form data'}), 400
    flash(_('Failed to post reply.'))
    return redirect(url_for('main.index'))
