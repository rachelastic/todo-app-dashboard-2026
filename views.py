from flask import Blueprint, render_template, redirect, url_for, flash, send_file
from flask import request
from flask_login import login_required, current_user
from models import db, Task, User, Visit, Waitlist, ErrorLog
from io import BytesIO, StringIO
import csv
import datetime
from collections import Counter

# Create a blueprint
main_blueprint = Blueprint('main', __name__)


def log_visit(page, user_id):
    """Log a visit to a page by a user."""
    visit = Visit(page=page, user=user_id)
    db.session.add(visit)
    db.session.commit()


###############################################################################
# Routes
###############################################################################


@main_blueprint.route('/', methods=['GET'])
def index():
    log_visit(page='index', user_id=current_user.id if current_user.is_authenticated else None)
    return render_template('index.html')

@main_blueprint.route('/invitation', methods=['GET', 'POST'])
def invitation():
    if request.method == 'GET':
        log_visit(page='invitation', user_id=current_user.id if current_user.is_authenticated else None)
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            existing = Waitlist.query.filter_by(email=email).first()
            if not existing:
                ip_address = request.remote_addr if request.remote_addr else None
                waitlist_entry = Waitlist(email=email, ip_address=ip_address)
                db.session.add(waitlist_entry)
                db.session.commit()
                log_visit(page='waitlist-signup', user_id=None)
    return render_template('invitation.html')


@main_blueprint.route('/todo', methods=['GET', 'POST'])
@login_required
def todo():
    log_visit(page='todo', user_id=current_user.id)
    return render_template('todo.html')


@main_blueprint.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    now = datetime.datetime.now()
    today = now.date()
    start_of_today = datetime.datetime.combine(today, datetime.time.min)
    end_of_today = start_of_today + datetime.timedelta(days=1)
    this_week_start = today - datetime.timedelta(days=6)
    this_week_start_dt = datetime.datetime.combine(this_week_start, datetime.time.min)
    prev_week_start_dt = this_week_start_dt - datetime.timedelta(days=7)

    # Today's visits (all pages)
    visits_today = Visit.query.filter(
        Visit.timestamp >= start_of_today,
        Visit.timestamp < end_of_today
    ).count()

    # New users this week (today and last 6 days)
    new_users = User.query.filter(
        User.created_at >= this_week_start_dt,
        User.created_at < end_of_today
    ).count()

    # Waitlist signups this week
    waitlist_count_this_week = Waitlist.query.filter(
        Waitlist.timestamp >= this_week_start_dt,
        Waitlist.timestamp < end_of_today
    ).count()

    total_users = User.query.count()

    # Index page visits: daily totals this week vs previous week
    week_dates = [this_week_start + datetime.timedelta(days=i) for i in range(7)]
    chart_week = [d.strftime('%a %d') for d in week_dates]
    week_visits = []
    two_week_visits = []
    for d in week_dates:
        day_start = datetime.datetime.combine(d, datetime.time.min)
        day_end = day_start + datetime.timedelta(days=1)
        count_this = Visit.query.filter(
            Visit.page == 'index',
            Visit.timestamp >= day_start,
            Visit.timestamp < day_end
        ).count()
        week_visits.append(count_this)
        prev_day_start = day_start - datetime.timedelta(days=7)
        prev_day_end = prev_day_start + datetime.timedelta(days=1)
        count_prev = Visit.query.filter(
            Visit.page == 'index',
            Visit.timestamp >= prev_day_start,
            Visit.timestamp < prev_day_end
        ).count()
        two_week_visits.append(count_prev)
    total_this_week = sum(week_visits)
    total_prev_week = sum(two_week_visits)
    if total_prev_week > 0:
        productivity_change = round((total_this_week - total_prev_week) / total_prev_week * 100, 1)
    else:
        productivity_change = 0.0 if total_this_week == 0 else 100.0

    # Placeholder for "New Users" chart (optional - reuse productivity_change for subtitle)
    week_notes = [0] * 7
    two_week_notes = [0] * 7
    if hasattr(User, 'created_at'):
        for i, d in enumerate(week_dates):
            day_start = datetime.datetime.combine(d, datetime.time.min)
            day_end = day_start + datetime.timedelta(days=1)
            week_notes[i] = User.query.filter(
                User.created_at >= day_start,
                User.created_at < day_end
            ).count()
            prev_day_start = day_start - datetime.timedelta(days=7)
            prev_day_end = prev_day_start + datetime.timedelta(days=1)
            two_week_notes[i] = User.query.filter(
                User.created_at >= prev_day_start,
                User.created_at < prev_day_end
            ).count()

    # Recent visits (~15) — full timestamp like "2026-02-25 16:09:12.503283+00:00: index"
    recent_visits_query = Visit.query.order_by(Visit.timestamp.desc()).limit(15).all()
    recent_visits = []
    for v in recent_visits_query:
        if v.timestamp:
            ts = v.timestamp.isoformat() if hasattr(v.timestamp, 'isoformat') else v.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')
            recent_visits.append({'page': v.page, 'date': ts})
        else:
            recent_visits.append({'page': v.page, 'date': 'N/A'})

    # Page visits today for bar chart
    today_visits_list = Visit.query.filter(
        Visit.timestamp >= start_of_today,
        Visit.timestamp < end_of_today
    ).all()
    page_counts = Counter(v.page for v in today_visits_list)
    page_visits_labels = list(page_counts.keys())
    page_visits_data = [page_counts[p] for p in page_visits_labels]

    # Database stats
    visits_count = Visit.query.count()
    users_count = User.query.count()
    tasks_count = Task.query.count()

    # Recent error logs
    error_logs = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(20).all()
    error_logs_formatted = [
        {'message': e.message, 'date': e.timestamp.strftime('%Y-%m-%d %H:%M') if e.timestamp else 'N/A', 'category': e.category or 'error'}
        for e in error_logs
    ]

    # Users list for "New User Information" (optional)
    users_list = []
    for u in User.query.all():
        users_list.append({
            'id': u.id,
            'name': u.email,
            'email': u.email,
            'date_created': u.created_at.strftime('%Y-%m-%d') if u.created_at else 'N/A',
            'tasks': u.tasks
        })

    # Waitlist list
    waitlist_entries = []
    for w in Waitlist.query.order_by(Waitlist.timestamp.desc()).all():
        waitlist_entries.append({
            'id': w.id,
            'email': w.email,
            'date': w.timestamp.strftime('%Y-%m-%d %H:%M') if w.timestamp else 'N/A',
            'ip_address': w.ip_address or 'N/A'
        })

    return render_template('admin.html',
                           date=now.strftime("%B %d, %Y"),
                           total_users=total_users,
                           new_users=new_users,
                           visits_today=visits_today,
                           waitlist_count_this_week=waitlist_count_this_week,
                           productivity_change=productivity_change,
                           chart_week=chart_week,
                           week_visits=week_visits,
                           two_week_visits=two_week_visits,
                           week_notes=week_notes,
                           two_week_notes=two_week_notes,
                           recent_visits=recent_visits,
                           page_visits_labels=page_visits_labels,
                           page_visits_data=page_visits_data,
                           visits_count=visits_count,
                           users_count=users_count,
                           tasks_count=tasks_count,
                           error_logs=error_logs_formatted,
                           users=users_list,
                           waitlist=waitlist_entries
                           )



@main_blueprint.route('/api/v1/tasks', methods=['GET'])
@login_required
def api_get_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return {
        "tasks": [task.to_dict() for task in tasks]
    }


@main_blueprint.route('/api/v1/tasks', methods=['POST'])
@login_required
def api_create_task():
    data = request.get_json()
    new_task = Task(title=data['title'], user_id=current_user.id)
    db.session.add(new_task)
    db.session.commit()
    log_visit(page='task-create', user_id=current_user.id)
    return {
        "task": new_task.to_dict()
    }, 201


@main_blueprint.route('/api/v1/tasks/<int:task_id>', methods=['PATCH'])
@login_required
def api_toggle_task(task_id):
    task = Task.query.get(task_id)

    if task is None:
        return {"error": "Task not found"}, 404

    task.toggle()
    db.session.commit()
    log_visit(page='task-toggle', user_id=current_user.id)
    return {"task": task.to_dict()}, 200


@main_blueprint.route('/remove/<int:task_id>')
@login_required
def remove(task_id):
    task = Task.query.get(task_id)

    if task is None:
        return redirect(url_for('main.todo'))

    db.session.delete(task)
    db.session.commit()
    log_visit(page='task-delete', user_id=current_user.id)
    return redirect(url_for('main.todo'))


###############################################################################
# Optional admin routes (referenced by admin.html)
###############################################################################


@main_blueprint.route('/backup')
def backup():
    """Optional: export key data as CSV."""
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['users', 'id', 'email', 'created_at'])
    for u in User.query.all():
        writer.writerow(['user', u.id, u.email, u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else ''])
    writer.writerow([])
    writer.writerow(['tasks', 'id', 'title', 'status', 'user_id'])
    for t in Task.query.all():
        writer.writerow(['task', t.id, t.title, t.status, t.user_id])
    writer.writerow([])
    writer.writerow(['waitlist', 'id', 'email', 'timestamp', 'ip_address'])
    for w in Waitlist.query.all():
        writer.writerow(['waitlist', w.id, w.email, w.timestamp.strftime('%Y-%m-%d %H:%M') if w.timestamp else '', w.ip_address or ''])
    writer.writerow([])
    writer.writerow(['visits', 'id', 'page', 'user_id', 'timestamp'])
    for v in Visit.query.all():
        writer.writerow(['visit', v.id, v.page, v.user or '', v.timestamp.strftime('%Y-%m-%d %H:%M') if v.timestamp else ''])
    buffer.seek(0)
    return send_file(
        BytesIO(buffer.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    )


@main_blueprint.route('/upload_db', methods=['POST'])
def upload_db():
    """Optional: placeholder for DB upload."""
    flash('Database upload is not implemented.', 'info')
    return redirect(url_for('main.dashboard'))


@main_blueprint.route('/waitlist_add/<int:entry_id>')
def waitlist_add(entry_id):
    """Optional: promote waitlist entry (e.g. redirect to signup with prefill)."""
    entry = Waitlist.query.get(entry_id)
    if not entry:
        flash('Waitlist entry not found.', 'error')
    else:
        flash(f'Add user from waitlist: {entry.email} (manual signup).', 'info')
    return redirect(url_for('main.dashboard'))


@main_blueprint.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    """Optional: delete a user and their tasks (admin)."""
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('main.dashboard'))
    if user_id == 1:
        flash('Cannot delete this user.', 'error')
        return redirect(url_for('main.dashboard'))
    for t in Task.query.filter_by(user_id=user_id).all():
        db.session.delete(t)
    Visit.query.filter_by(user=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'info')
    return redirect(url_for('main.dashboard'))