"""Admin routes - all admin endpoints registered on the admin Blueprint."""

import os

import requests
from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from admin import bp
from admin.auth import hash_password, login_required
from admin.export import DataExporter
from admin.llm import generate_source_code
from admin.security import load_custom_source
from admin.utils import (
    _clean_llm_artifacts,
    _mask_api_key,
    load_sources_config,
    regenerate_frontend,
    save_sources_config,
)
from generator.html_generator import HTMLGenerator
from scraper.sources import SOURCE_REGISTRY
from scraper.sources.framework import ScraperFramework
from storage.sqlite_store import SQLiteStore


def _get_db_path():
    return current_app.config.get("DATABASE_PATH", "custom_crawler.db")


def _get_project_root():
    return current_app.config.get(
        "PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


# ============ Auth ============


@bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """Login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("用户名和密码不能为空")
            return render_template("login.html")

        store = SQLiteStore(_get_db_path())
        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role FROM admin_users WHERE username = ?",
            (username,),
        )
        user = cursor.fetchone()

        if user and user[2] == hash_password(password):
            store.add_audit_log(
                action="LOGIN_SUCCESS",
                username=username,
                ip_address=request.remote_addr,
            )
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[3]
            flash(f"欢迎, {user[1]}!")
            return redirect(url_for("admin.admin_index"))
        else:
            store.add_audit_log(
                action="LOGIN_FAILED",
                username=username,
                ip_address=request.remote_addr,
                details="Invalid credentials",
            )
            flash("用户名或密码错误")

    return render_template("login.html")


@bp.route("/logout")
def admin_logout():
    """Logout."""
    username = session.get("username")
    if username:
        store = SQLiteStore(_get_db_path())
        store.add_audit_log(
            action="LOGOUT",
            username=username,
            ip_address=request.remote_addr,
        )
    session.clear()
    flash("已退出登录")
    return redirect(url_for("admin.admin_login"))


# ============ Dashboard ============


@bp.route("/")
@login_required
def admin_index():
    store = SQLiteStore(_get_db_path())
    stats = store.get_stats()
    languages = store.get_languages()
    sources = store.get_sources()
    return render_template(
        "dashboard.html", stats=stats, languages=languages, sources=sources
    )


@bp.route("/stats")
@login_required
def admin_stats():
    store = SQLiteStore(_get_db_path())
    return jsonify(store.get_stats())


# ============ Projects ============


@bp.route("/projects")
@login_required
def admin_projects():
    store = SQLiteStore(_get_db_path())
    page = request.args.get("page", 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    search = request.args.get("search", "", type=str)
    language = request.args.get("language", "", type=str)
    source = request.args.get("source", "", type=str)

    projects = store.get_all(
        source=source if source else None,
        language=language if language else None,
        search=search if search else None,
        limit=per_page,
        offset=offset,
        sort_by="scraped_at",
        sort_order="DESC",
    )
    total = store.get_count(
        source=source if source else None,
        language=language if language else None,
        search=search if search else None,
    )
    languages = store.get_languages()
    sources = store.get_sources()

    return render_template(
        "projects.html",
        projects=projects,
        page=page,
        total=total,
        per_page=per_page,
        search=search,
        language=language,
        source=source,
        languages=languages,
        sources=sources,
    )


@bp.route("/project/<int:project_id>", methods=["GET", "POST"])
@login_required
def admin_edit_project(project_id):
    store = SQLiteStore(_get_db_path())
    project = store.get_by_id(project_id)
    if not project:
        flash("项目不存在")
        return redirect(url_for("admin.admin_projects"))

    if request.method == "POST":
        store.update(
            project_id,
            description=request.form.get("description", ""),
            project_url=request.form.get("project_url", ""),
            stars=request.form.get("stars", 0, type=int),
            language=request.form.get("language", ""),
            author=request.form.get("author", ""),
        )
        flash("项目更新成功")
        return redirect(url_for("admin.admin_projects"))

    languages = store.get_languages()
    return render_template("edit_project.html", project=project, languages=languages)


@bp.route("/delete/<int:project_id>", methods=["GET", "POST"])
@login_required
def admin_delete_project(project_id):
    store = SQLiteStore(_get_db_path())
    project = store.get_by_id(project_id)
    if not project:
        flash("项目不存在")
        return redirect(url_for("admin.admin_projects"))

    if request.method == "POST":
        store.add_audit_log(
            action="DELETE_PROJECT",
            username=session.get("username"),
            resource_type="project",
            resource_id=project_id,
            details=f"Deleted project: {project.project_name}",
            ip_address=request.remote_addr,
        )
        store.delete(project_id)
        flash("项目删除成功")
        return redirect(url_for("admin.admin_projects"))

    return render_template("delete_project.html", project=project)


@bp.route("/projects/batch-delete", methods=["POST"])
@login_required
def admin_batch_delete():
    store = SQLiteStore(_get_db_path())
    ids_str = request.form.get("ids", "")
    if ids_str:
        ids = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
        deleted = 0
        for pid in ids:
            if store.delete(pid):
                deleted += 1
        store.add_audit_log(
            action="BATCH_DELETE_PROJECTS",
            username=session.get("username"),
            details=f"Deleted {deleted} projects",
            ip_address=request.remote_addr,
        )
        flash(f"已删除 {deleted} 个项目")
    else:
        flash("未选择任何项目")
    return redirect(url_for("admin.admin_projects"))


@bp.route("/project/new", methods=["GET", "POST"])
@login_required
def admin_new_project():
    store = SQLiteStore(_get_db_path())
    sources = store.get_sources()
    languages = store.get_languages()

    if request.method == "POST":
        project_name = request.form.get("project_name", "").strip()
        project_url = request.form.get("project_url", "").strip()
        description = request.form.get("description", "")
        author = request.form.get("author", "")
        stars = request.form.get("stars", 0, type=int)
        language = request.form.get("language", "")
        source = request.form.get("source", "manual")

        if not project_name or not project_url:
            flash("项目名称和URL不能为空")
            return render_template(
                "new_project.html", sources=sources, languages=languages
            )

        from datetime import datetime

        from scraper.sources.models import UnifiedProject

        project = UnifiedProject(
            source=source,
            project_name=project_name,
            project_url=project_url,
            description=description,
            author=author,
            stars=stars,
            forks=0,
            language=language,
            category="",
            scraped_at=datetime.now(),
        )
        store.insert(project)
        flash("项目创建成功")
        return redirect(url_for("admin.admin_projects"))

    return render_template("new_project.html", sources=sources, languages=languages)


# ============ Sources ============


@bp.route("/sources")
@login_required
def admin_sources():
    config = load_sources_config()
    builtin_sources = config.get("sources", {})

    store = SQLiteStore(_get_db_path())
    custom_sources = store.get_all_custom_sources()
    health_data = {h["source_name"]: h for h in store.get_all_source_health()}

    all_sources = []

    for source_id, source_config in builtin_sources.items():
        all_sources.append(
            {
                "name": source_id,
                "type": "builtin",
                "enabled": source_config.get("enabled", False),
                "schedule_interval": source_config.get("schedule_interval", 0),
                "url": source_config.get("url", source_config.get("api_url", "")),
                "description": "内置数据源",
                "health": health_data.get(source_id),
            }
        )

    for source in custom_sources:
        all_sources.append(
            {
                "name": source["name"],
                "type": "custom",
                "enabled": source.get("enabled", False),
                "schedule_interval": source.get("schedule_interval", 0),
                "url": "",
                "description": source.get("description", ""),
                "created_at": source.get("created_at", ""),
                "health": health_data.get(source["name"]),
            }
        )

    return render_template("sources.html", sources=all_sources)


@bp.route("/sources/batch-toggle", methods=["POST"])
@login_required
def admin_batch_toggle_sources():
    data = request.get_json()
    sources = data.get("sources", [])
    enable = data.get("enable", True)
    if not sources:
        return jsonify({"success": False, "error": "未选择数据源"})
    store = SQLiteStore(_get_db_path())
    config = load_sources_config()
    config_sources = config.get("sources", {})
    count = 0
    for source in sources:
        name = source.get("name")
        source_type = source.get("type")
        if source_type == "builtin" and name in config_sources:
            config_sources[name]["enabled"] = enable
            count += 1
        elif source_type == "custom":
            store.toggle_custom_source(name, enable)
            count += 1
    save_sources_config(config)
    return jsonify({"success": True, "count": count})


@bp.route("/sources/toggle", methods=["POST"])
@login_required
def admin_toggle_source():
    source_id = request.form.get("source_id", "")
    config = load_sources_config()
    sources = config.get("sources", {})

    if source_id in sources:
        current = sources[source_id].get("enabled", False)
        sources[source_id]["enabled"] = not current
        save_sources_config(config)
        status = "已启用" if sources[source_id]["enabled"] else "已禁用"
        flash(f"数据源 '{source_id}' {status}")
    else:
        flash(f"数据源 '{source_id}' 不存在")

    return redirect(url_for("admin.admin_sources"))


@bp.route("/sources/schedule", methods=["POST"])
@login_required
def admin_set_schedule():
    source_id = request.form.get("source_id", "")
    interval = request.form.get("interval", "")

    config = load_sources_config()
    sources = config.get("sources", {})

    if source_id in sources:
        try:
            interval_minutes = int(interval) if interval else 0
            sources[source_id]["schedule_interval"] = interval_minutes
            save_sources_config(config)
            if interval_minutes > 0:
                flash(f"数据源 '{source_id}' 将每 {interval_minutes} 分钟刷新一次")
            else:
                flash(f"已取消数据源 '{source_id}' 的定时刷新")
        except ValueError:
            flash("刷新间隔值无效")
        return redirect(url_for("admin.admin_sources"))

    store = SQLiteStore(_get_db_path())
    custom_source = store.get_custom_source(source_id)
    if custom_source:
        try:
            interval_minutes = int(interval) if interval else 0
            store.update_custom_source_schedule(source_id, interval_minutes)
            if interval_minutes > 0:
                flash(
                    f"自定义数据源 '{source_id}' 将每 {interval_minutes} 分钟刷新一次"
                )
            else:
                flash(f"已取消自定义数据源 '{source_id}' 的定时刷新")
        except ValueError:
            flash("刷新间隔值无效")
        return redirect(url_for("admin.admin_sources"))

    flash(f"数据源 '{source_id}' 不存在")
    return redirect(url_for("admin.admin_sources"))


# ============ Refresh ============


@bp.route("/refresh/<source>", methods=["POST"])
@login_required
def admin_refresh_source(source):
    valid_sources = list(SOURCE_REGISTRY.keys())
    if source not in valid_sources:
        flash(f"无效的数据源: {source}")
        return redirect(url_for("admin.admin_index"))

    try:
        config_path = os.path.join(_get_project_root(), "config", "sources.yaml")
        framework = ScraperFramework(config_path=config_path, db_path=_get_db_path())
        projects = framework.scrape_source(source)

        success, count = regenerate_frontend(_get_db_path())
        if success:
            flash(
                f"已刷新 {source}: 采集 {len(projects)} 条，前台已更新 ({count} 项)"
            )
        else:
            flash(
                f"已刷新 {source}: 采集 {len(projects)} 条，但前台更新失败: {count}"
            )
    except requests.exceptions.ConnectionError:
        flash("网络不可达，请检查网络或代理设置")
    except Exception as e:
        flash(f"刷新 {source} 失败: {str(e)}")
    return redirect(url_for("admin.admin_index"))


@bp.route("/refresh-all", methods=["POST"])
@login_required
def admin_refresh_all():
    import threading
    import json
    import sys
    import traceback
    from datetime import datetime
    from flask import current_app

    # 在主线程中获取所有依赖（避免线程中使用 Flask 上下文）
    db_path = _get_db_path()
    project_root = _get_project_root()
    app = current_app._get_current_object()  # 获取真实 app 对象（非代理）

    # 在主线程中设置初始状态
    store = SQLiteStore(db_path)
    store.set_setting(
        "refresh_task_status",
        json.dumps(
            {
                "status": "running",
                "started_at": None,
                "message": "正在刷新所有数据源...",
            }
        ),
    )
    store.close()

    def _refresh_job():
        # 在后台线程中使用真实 app 对象创建应用上下文
        with app.app_context():
            thread_store = SQLiteStore(db_path)
            try:
                started_at = datetime.now().isoformat()
                thread_store.set_setting(
                    "refresh_task_status",
                    json.dumps(
                        {
                            "status": "running",
                            "started_at": started_at,
                            "message": "正在刷新所有数据源...",
                        }
                    ),
                )

                config_path = os.path.join(project_root, "config", "sources.yaml")
                framework = ScraperFramework(config_path=config_path, db_path=db_path)
                projects = framework.scrape_all()

                regenerate_frontend(db_path)

                # 任务完成
                thread_store.set_setting(
                    "refresh_task_status",
                    json.dumps(
                        {
                            "status": "completed",
                            "started_at": started_at,
                            "completed_at": datetime.now().isoformat(),
                            "message": f"刷新完成！共获取 {len(projects)} 个项目，前台页面已更新",
                        }
                    ),
                )
            except Exception as e:
                # 获取完整堆栈信息
                error_trace = traceback.format_exc()
                print(
                    f"[REFRESH ERROR] {datetime.now().isoformat()}: {e}",
                    file=sys.stderr,
                )
                print(error_trace, file=sys.stderr)
                # 任务失败
                thread_store.set_setting(
                    "refresh_task_status",
                    json.dumps(
                        {
                            "status": "failed",
                            "error": str(e),
                            "traceback": error_trace,
                            "message": f"刷新失败：{str(e)}",
                        }
                    ),
                )
            finally:
                thread_store.close()

    threading.Thread(target=_refresh_job, daemon=True).start()
    flash("正在后台刷新所有数据源并重新生成前台，请稍候刷新页面查看结果")
    return redirect(url_for("admin.admin_index"))


@bp.route("/refresh-status")
@login_required
def admin_refresh_status():
    """Get the status of the background refresh task."""
    import json

    store = SQLiteStore(_get_db_path())
    status_str = store.get_setting("refresh_task_status", "")
    if status_str:
        try:
            status = json.loads(status_str)
            return jsonify(status)
        except json.JSONDecodeError:
            pass
    return jsonify({"status": "idle", "message": "无进行中的任务"})


@bp.route("/regenerate-frontend", methods=["POST"])
@login_required
def admin_regenerate_frontend():
    try:
        store = SQLiteStore(_get_db_path())
        projects = store.get_all()

        if not projects:
            flash("数据库中没有项目数据，无法生成前台页面")
            return redirect(url_for("admin.admin_index"))

        from admin.utils import OUTPUT_DIR

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "index.html")
        generator = HTMLGenerator()
        generator.generate(projects, output_path)

        flash(f"前台页面已更新 ({len(projects)} 个项目)")
    except Exception as e:
        flash(f"前台页面更新失败: {str(e)}")

    return redirect(url_for("admin.admin_index"))


# ============ Exports ============


@bp.route("/exports")
@login_required
def admin_exports():
    store = SQLiteStore(_get_db_path())
    languages = store.get_languages()
    sources = store.get_sources()
    total = store.get_count()
    language = request.args.get("language", "", type=str)
    source = request.args.get("source", "", type=str)
    return render_template(
        "exports.html",
        total=total,
        languages=languages,
        sources=sources,
        language=language,
        source=source,
    )


@bp.route("/exports/<format>")
@login_required
def admin_export_data(format):
    store = SQLiteStore(_get_db_path())
    language = request.args.get("language", "", type=str)
    source = request.args.get("source", "", type=str)
    projects = store.get_all(
        language=language if language else None, source=source if source else None
    )

    formats = {
        "json": ("application/json", "github-trending.json", DataExporter.to_json),
        "csv": ("text/csv", "github-trending.csv", DataExporter.to_csv),
        "markdown": (
            "text/markdown",
            "github-trending.md",
            DataExporter.to_markdown,
        ),
        "txt": ("text/plain", "github-trending.txt", DataExporter.to_txt),
    }
    if format not in formats:
        flash(f"不支持的导出格式: {format}")
        return redirect(url_for("admin.admin_exports"))
    mimetype, filename, func = formats[format]
    content = func(projects)
    response = current_app.response_class(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
    return response


# ============ Logs ============


@bp.route("/audit-log")
@login_required
def admin_audit_log():
    if session.get("role") != "admin":
        flash("只有管理员可以查看审计日志")
        return redirect(url_for("admin.admin_index"))
    store = SQLiteStore(_get_db_path())
    logs = store.get_audit_log(limit=100)
    return render_template("audit_log.html", logs=logs)


@bp.route("/source-logs")
@login_required
def admin_source_logs():
    store = SQLiteStore(_get_db_path())
    page = request.args.get("page", 1, type=int)
    per_page = 50
    source_name = request.args.get("source", "", type=str)
    logs = store.get_scrape_logs(
        source_name=source_name if source_name else None,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    sources = store.get_sources()
    return render_template(
        "source_logs.html",
        logs=logs,
        page=page,
        per_page=per_page,
        source_name=source_name,
        sources=sources,
    )


# ============ User Management ============


@bp.route("/users")
@login_required
def admin_users():
    if session.get("role") != "admin":
        flash("只有管理员可以访问用户管理")
        return redirect(url_for("admin.admin_index"))

    store = SQLiteStore(_get_db_path())
    conn = store._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM admin_users ORDER BY id")
    users = cursor.fetchall()
    return render_template("users.html", users=users)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
def admin_new_user():
    if session.get("role") != "admin":
        flash("只有管理员可以添加用户")
        return redirect(url_for("admin.admin_index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if not username or not password:
            flash("用户名和密码不能为空")
            return render_template("user_form.html", user=None, action="创建")

        store = SQLiteStore(_get_db_path())
        conn = store._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM admin_users WHERE username = ?", (username,))
        if cursor.fetchone():
            flash("用户名已存在")
            return render_template("user_form.html", user=None, action="创建")

        cursor.execute(
            "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role),
        )
        conn.commit()
        flash(f"用户 '{username}' 创建成功")
        return redirect(url_for("admin.admin_users"))

    return render_template("user_form.html", user=None, action="创建")


@bp.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
def admin_edit_user(user_id):
    if session.get("role") != "admin":
        flash("只有管理员可以编辑用户")
        return redirect(url_for("admin.admin_index"))

    store = SQLiteStore(_get_db_path())
    conn = store._get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if password:
            cursor.execute(
                "UPDATE admin_users SET password_hash = ?, role = ? WHERE id = ?",
                (hash_password(password), role, user_id),
            )
        else:
            cursor.execute(
                "UPDATE admin_users SET role = ? WHERE id = ?", (role, user_id)
            )
        conn.commit()
        flash("用户更新成功")
        return redirect(url_for("admin.admin_users"))

    cursor.execute(
        "SELECT id, username, role FROM admin_users WHERE id = ?", (user_id,)
    )
    user = cursor.fetchone()
    if not user:
        flash("用户不存在")
        return redirect(url_for("admin.admin_users"))

    return render_template("user_form.html", user=user, action="编辑")


@bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    if session.get("role") != "admin":
        flash("只有管理员可以删除用户")
        return redirect(url_for("admin.admin_index"))

    if user_id == session.get("user_id"):
        flash("不能删除当前登录用户")
        return redirect(url_for("admin.admin_users"))

    store = SQLiteStore(_get_db_path())
    conn = store._get_connection()
    cursor = conn.cursor()
    store.add_audit_log(
        action="DELETE_USER",
        username=session.get("username"),
        resource_type="user",
        resource_id=user_id,
        ip_address=request.remote_addr,
    )
    cursor.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
    conn.commit()
    flash("用户已删除")
    return redirect(url_for("admin.admin_users"))


# ============ Custom Sources ============


@bp.route("/custom-sources")
@login_required
def admin_custom_sources():
    return redirect(url_for("admin.admin_sources"))


@bp.route("/custom-source/new", methods=["GET"])
@login_required
def admin_custom_source_new():
    return render_template(
        "custom_source_form.html",
        source=None,
        generated_code=None,
        error=None,
        name="",
        description="",
    )


@bp.route("/custom-source/edit", methods=["POST"])
@login_required
def admin_custom_source_edit():
    name = request.form.get("name", "").strip()
    store = SQLiteStore(_get_db_path())
    source = store.get_custom_source(name)

    if source:
        return render_template(
            "custom_source_form.html",
            source=source,
            generated_code=source["source_code"],
            error=None,
            name=name,
            description=source["description"],
        )

    builtin_file = os.path.join(_get_project_root(), "scraper", "sources", f"{name}.py")
    if os.path.exists(builtin_file):
        with open(builtin_file, "r", encoding="utf-8") as f:
            source_code = f.read()
        return render_template(
            "custom_source_form.html",
            source=None,
            generated_code=source_code,
            error=None,
            name=name,
            description=f"内置数据源: {name}",
        )

    flash(f"数据源 '{name}' 不存在")
    return redirect(url_for("admin.admin_sources"))


@bp.route("/custom-source/generate", methods=["POST"])
@login_required
def admin_custom_source_generate():
    description = request.form.get("description", "").strip()
    source_name = request.form.get("name", "").strip()
    extra_prompt = request.form.get("prompt_hint", "").strip()

    if not description:
        flash("请描述爬虫的功能")
        return redirect(url_for("admin.admin_custom_source_new"))

    if not source_name:
        flash("请输入数据源名称")
        return redirect(url_for("admin.admin_custom_source_new"))

    store = SQLiteStore(_get_db_path())
    existing = store.get_custom_source(source_name)
    if existing:
        flash(f"数据源 '{source_name}' 已存在")
        return redirect(url_for("admin.admin_custom_source_new"))

    try:
        generated_code = generate_source_code(source_name, description, extra_prompt)
        if not generated_code:
            flash("生成结果为空，请重试")
            return redirect(url_for("admin.admin_custom_source_new"))

        return render_template(
            "custom_source_form.html",
            source=None,
            generated_code=generated_code,
            error=None,
            name=source_name,
            description=description,
            prompt_hint=extra_prompt,
        )
    except Exception as e:
        flash(f"生成失败: {str(e)}")
        return redirect(url_for("admin.admin_custom_source_new"))


@bp.route("/custom-source/save", methods=["POST"])
@login_required
def admin_custom_source_save():
    name = request.form.get("name", "").strip()
    source_code = request.form.get("source_code", "").strip()
    description = request.form.get("description", "").strip()

    if not name or not source_code:
        flash("名称和代码不能为空")
        return redirect(url_for("admin.admin_custom_source_new"))

    source_code = source_code.replace(
        "from .base import", "from scraper.sources.base import"
    )
    source_code = source_code.replace(
        "from .models import", "from scraper.sources.models import"
    )
    source_code = source_code.replace(
        "from . import register_source", "from scraper.sources import register_source"
    )

    source_code = _clean_llm_artifacts(source_code)

    try:
        store = SQLiteStore(_get_db_path())
        store.save_custom_source(name, source_code, description)

        success, msg = load_custom_source(name, source_code)
        if success:
            flash(f"数据源 '{name}' 保存成功并已加载")
        else:
            flash(f"数据源 '{name}' 保存成功，但加载失败: {msg}")
    except Exception as e:
        flash(f"保存失败: {str(e)}")

    return redirect(url_for("admin.admin_sources"))


@bp.route("/custom-source/test", methods=["POST"])
@login_required
def admin_custom_source_test():
    name = request.form.get("name", "").strip()

    store = SQLiteStore(_get_db_path())
    source = store.get_custom_source(name)

    if not source:
        flash(f"数据源 '{name}' 不存在")
        return redirect(url_for("admin.admin_sources"))

    if name in SOURCE_REGISTRY:
        source_class = SOURCE_REGISTRY[name]
    else:
        source_code = _clean_llm_artifacts(source["source_code"])
        success, _ = load_custom_source(name, source_code)
        if not success:
            flash(f"无法加载数据源 '{name}'")
            return redirect(url_for("admin.admin_sources"))
        source_class = SOURCE_REGISTRY.get(name)

    if not source_class:
        flash(f"数据源 '{name}' 未注册")
        return redirect(url_for("admin.admin_sources"))

    try:
        instance = source_class(priority=10)
        projects = instance.scrape()

        if projects:
            inserted = store.insert_many(projects)
            flash(f"测试成功: 采集 {len(projects)} 条，入库 {inserted} 条")
        else:
            flash(
                "测试失败: scrape() 返回空列表，未采集到任何数据，请检查 XPath 选择器是否正确"
            )
    except requests.exceptions.ConnectionError:
        flash("网络不可达，请检查网络或代理设置")
    except Exception as e:
        flash(f"测试失败: {str(e)}")

    return redirect(url_for("admin.admin_sources"))


@bp.route("/custom-source/delete", methods=["POST"])
@login_required
def admin_custom_source_delete():
    name = request.form.get("name", "").strip()

    if name in SOURCE_REGISTRY:
        del SOURCE_REGISTRY[name]

    store = SQLiteStore(_get_db_path())
    store.delete_custom_source(name)

    flash(f"数据源 '{name}' 已删除")
    return redirect(url_for("admin.admin_sources"))


@bp.route("/source/test", methods=["POST"])
@login_required
def admin_source_test():
    name = request.form.get("name", "").strip()
    if not name:
        flash("数据源名称不能为空")
        return redirect(url_for("admin.admin_sources"))

    store = SQLiteStore(_get_db_path())
    source_class = SOURCE_REGISTRY.get(name)

    if not source_class:
        custom_source = store.get_custom_source(name)
        if custom_source and custom_source.get("source_code"):
            source_code = _clean_llm_artifacts(custom_source["source_code"])
            success, _ = load_custom_source(name, source_code)
            if success:
                source_class = SOURCE_REGISTRY.get(name)

    if not source_class:
        flash(f"数据源 '{name}' 未注册或不存在")
        return redirect(url_for("admin.admin_sources"))

    try:
        instance = source_class(priority=10)
        projects = instance.scrape()
        if projects:
            inserted = store.insert_many(projects)
            flash(f"测试成功: 采集 {len(projects)} 条，入库 {inserted} 条")
        else:
            flash(
                "测试失败: scrape() 返回空列表，未采集到任何数据，请检查 XPath 选择器是否正确"
            )
    except requests.exceptions.ConnectionError:
        flash("网络不可达，请检查网络或代理设置")
    except Exception as e:
        flash(f"测试失败: {str(e)}")

    return redirect(url_for("admin.admin_sources"))


@bp.route("/source/delete", methods=["POST"])
@login_required
def admin_source_delete():
    name = request.form.get("name", "").strip()
    if not name:
        flash("数据源名称不能为空")
        return redirect(url_for("admin.admin_sources"))

    if name in SOURCE_REGISTRY:
        del SOURCE_REGISTRY[name]

    store = SQLiteStore(_get_db_path())

    custom_source = store.get_custom_source(name)
    if custom_source:
        store.delete_custom_source(name)
        flash(f"数据源 '{name}' 已删除")
    else:
        config = load_sources_config()
        sources = config.get("sources", {})
        if name in sources:
            del sources[name]
            save_sources_config(config)
            flash(f"内置数据源 '{name}' 已删除")
        else:
            flash(f"数据源 '{name}' 不存在")

    return redirect(url_for("admin.admin_sources"))


# ============ Settings ============


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    store = SQLiteStore(_get_db_path())

    if request.method == "POST":
        provider = request.form.get("provider", "openai").strip()
        if provider not in ("openai", "anthropic"):
            provider = "openai"

        base_url = request.form.get("base_url", "").strip()
        api_key = request.form.get("api_key", "").strip()
        model = request.form.get("model", "").strip()

        if not api_key or "..." in api_key:
            api_key = store.get_setting("llm_api_key", "")
        else:
            if api_key.startswith("env:"):
                env_var = api_key[4:]
                api_key = os.environ.get(env_var, "")

        store.set_setting("llm_provider", provider)
        store.set_setting("llm_base_url", base_url)
        store.set_setting("llm_api_key", api_key)
        store.set_setting("llm_model", model)

        flash("设置已保存")
        return redirect(url_for("admin.admin_settings"))

    provider = store.get_setting("llm_provider", "openai")
    if provider not in ("openai", "anthropic"):
        provider = "openai"

    base_url = store.get_setting("llm_base_url", "")
    api_key = store.get_setting("llm_api_key", "")
    model = store.get_setting("llm_model", "")

    masked_api_key = _mask_api_key(api_key)

    return render_template(
        "settings.html",
        provider=provider,
        base_url=base_url,
        api_key=masked_api_key,
        model=model,
    )


@bp.route("/settings/test-api", methods=["POST"])
@login_required
def admin_settings_test_api():
    data = request.get_json()
    provider = data.get("provider", "openai")
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")

    if api_key and "..." in api_key:
        store = SQLiteStore(_get_db_path())
        saved_key = store.get_setting("llm_api_key", "")
        if saved_key:
            api_key = saved_key

    if not api_key:
        return jsonify({"success": False, "error": "API Key 不能为空"})

    system_prompt = "你是一个有用的助手。"
    user_prompt = "说 '测试成功' 确认连接正常。"

    try:
        if provider == "anthropic":
            endpoint = (base_url or "https://api.anthropic.com") + "/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": model or "claude-sonnet-4-20250514",
                "max_tokens": 100,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        else:
            endpoint = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "model": model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 100,
            }

        from admin.llm_api import _call_llm_api

        response = _call_llm_api(endpoint, headers, payload, timeout=30)
        result = response.json()

        if provider == "anthropic":
            reply = result["content"][0]["text"]
        else:
            reply = result["choices"][0]["message"].get("content", "")

        return jsonify({"success": True, "reply": reply})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
