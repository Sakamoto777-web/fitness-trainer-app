# ===== モジュールのインポート =====
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from flask_migrate import Migrate
import pytz
from PIL import Image, ImageOps
import io

# ===== 基本設定とFlaskアプリケーションのインスタンス作成 =====
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# ===== アプリケーション設定 =====
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'oHKNxg+xByWfyDOIXMBW1GAX34XdqelW'

# ファイルアップロード設定
UPLOAD_FOLDER = 'static/uploads/messages'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB制限
TARGET_SIZE = 300 * 1024  # 300KB目標サイズ

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# アップロードフォルダの作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 日本時間の設定
JST = pytz.timezone('Asia/Tokyo')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ===== ユーティリティ関数 =====
def get_jst_now():
    """日本時間の現在時刻を取得"""
    return datetime.now(JST)

def allowed_file(filename):
    """許可されたファイル形式かチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_file, target_size=TARGET_SIZE, max_dimension=800):
    """画像を圧縮してファイルサイズを削減"""
    try:
        # 画像を開く
        image = Image.open(image_file)
        
        # EXIF情報に基づいて画像を正しい向きに回転
        image = ImageOps.exif_transpose(image)
        
        # RGBAをRGBに変換（JPEGは透明度をサポートしないため）
        if image.mode in ('RGBA', 'P'):
            # 白い背景を作成
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # 画像サイズを調整（長辺をmax_dimensionに制限）
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # 圧縮品質を調整してサイズを削減
        quality = 85
        while quality > 10:
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            
            # ファイルサイズをチェック
            if output.tell() <= target_size:
                break
            
            quality -= 5
        
        output.seek(0)
        return output, quality
        
    except Exception as e:
        print(f"画像圧縮エラー: {e}")
        return None, None

def save_compressed_image(file, filename):
    """圧縮された画像を保存"""
    try:
        compressed_image, quality = compress_image(file)
        if compressed_image:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(file_path, 'wb') as f:
                f.write(compressed_image.read())
            print(f"画像を圧縮して保存: {filename} (品質: {quality})")
            return True
        return False
    except Exception as e:
        print(f"画像保存エラー: {e}")
        return False

# ===== モデル定義 =====
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    height = db.Column(db.Float, nullable=True)
    age_group = db.Column(db.String(50), nullable=True)
    is_public_weight = db.Column(db.Boolean, default=False, nullable=False)
    target_weight = db.Column(db.Float, nullable=True)
    
    # リレーションシップ定義
    sleep_logs = db.relationship('SleepLog', backref='student', lazy=True, cascade='all, delete-orphan')
    bowel_movement_logs = db.relationship('BowelMovementLog', backref='student', lazy=True, cascade='all, delete-orphan')
    weight_logs = db.relationship('WeightLog', backref='student', lazy=True, cascade='all, delete-orphan')
    meal_logs = db.relationship('MealLog', backref='student', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Student('{self.nickname}', '{self.email}')"

class SleepLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=lambda: get_jst_now().date())
    duration = db.Column(db.Float, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    def __repr__(self):
        return f"SleepLog(Date: {self.log_date}, Duration: {self.duration}h for StudentID: {self.student_id})"

class BowelMovementLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=lambda: get_jst_now().date())
    occurred = db.Column(db.Boolean, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    def __repr__(self):
        return f"BowelMovementLog(Date: {self.log_date}, Occurred: {self.occurred} for StudentID: {self.student_id})"

class WeightLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=lambda: get_jst_now().date())
    weight = db.Column(db.Float, nullable=False)
    body_fat_percentage = db.Column(db.Float, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    def __repr__(self):
        return f"WeightLog(Date: {self.log_date}, W: {self.weight}kg, BF: {self.body_fat_percentage}% for SID: {self.student_id})"

class MealLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_datetime = db.Column(db.DateTime, nullable=False, default=get_jst_now)
    meal_type = db.Column(db.String(20), nullable=False, default='morning')
    description = db.Column(db.Text, nullable=True)
    total_calories = db.Column(db.Integer, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    
    def __repr__(self):
        return f"MealLog(DateTime: {self.meal_datetime}, Type: {self.meal_type}, Cal: {self.total_calories} for SID: {self.student_id})"

class Trainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    def __repr__(self):
        return f"Trainer('{self.name}', '{self.email}')"

# app.py内のMessageクラス定義で、created_atのデフォルト値を修正

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_type = db.Column(db.String(20), nullable=False)  # 'student' or 'trainer'
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_type = db.Column(db.String(20), nullable=False)  # 'student' or 'trainer'
    receiver_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)  # 会話の対象となる生徒
    trainer_id = db.Column(db.Integer, db.ForeignKey('trainer.id'), nullable=False)  # 会話の対象となるトレーナー
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), nullable=False, default='general')  # 'general', 'advice', 'question', 'encouragement'
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    
    # タイムゾーンなしの日時で保存（JSTとして扱う）
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: get_jst_now().replace(tzinfo=None))
    
    # 新機能用フィールド
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    
    # リレーションシップ
    student = db.relationship('Student', backref='student_messages')
    trainer = db.relationship('Trainer', backref='trainer_messages')
    
    def delete_message(self):
        """メッセージを論理削除"""
        self.is_deleted = True
        self.deleted_at = get_jst_now().replace(tzinfo=None)  # タイムゾーンなしで保存
        db.session.commit()
    
    def can_delete(self, user_type, user_id):
        """削除権限チェック（送信から30分以内かつ送信者本人）"""
        try:
            # 既に削除されている場合は削除不可
            if self.is_deleted:
                return False
            
            # 送信者本人かチェック
            if self.sender_type != user_type or self.sender_id != user_id:
                return False
            
            # 送信から30分以内かチェック（両方ともタイムゾーンなしで比較）
            from datetime import timedelta
            time_limit = self.created_at + timedelta(minutes=30)
            current_time = get_jst_now().replace(tzinfo=None)  # タイムゾーンを削除
            
            return current_time < time_limit
            
        except Exception as e:
            print(f"can_delete エラー: {str(e)}")
            return False
    
    def __repr__(self):
        return f"Message(From: {self.sender_type}_{self.sender_id} To: {self.receiver_type}_{self.receiver_id}, Type: {self.message_type})"

# ===== ルート定義 =====

@app.route('/')
def home():
    current_nickname = session.get('nickname')
    
    # 体重公開を許可している生徒の最新の体重データを取得
    subquery = db.session.query(
        WeightLog.student_id,
        db.func.max(WeightLog.log_date).label('max_log_date')
    ).group_by(WeightLog.student_id).subquery()

    public_weight_data = db.session.query(
        Student,
        WeightLog
    ).join(WeightLog, Student.id == WeightLog.student_id).join(
        subquery,
        db.and_(
            WeightLog.student_id == subquery.c.student_id,
            WeightLog.log_date == subquery.c.max_log_date
        )
    ).filter(Student.is_public_weight == True).order_by(Student.nickname).all()

    display_data = []
    for student, weight_log in public_weight_data:
        # 目標体重情報
        if student.target_weight is not None:
            diff_abs = abs(weight_log.weight - student.target_weight)
            if weight_log.weight > student.target_weight:
                target_info = f"目標: {student.target_weight:.1f}kg (あと {diff_abs:.1f}kg 減)"
                target_status = "losing"
            elif weight_log.weight < student.target_weight:
                target_info = f"目標: {student.target_weight:.1f}kg (あと {diff_abs:.1f}kg 増)"
                target_status = "gaining"
            else:
                target_info = f"目標: {student.target_weight:.1f}kg (🎉 達成！)"
                target_status = "achieved"
        else:
            target_info = "目標未設定"
            target_status = "none"

        # 継続日数の計算（最初の体重記録から現在まで）
        first_weight = WeightLog.query.filter_by(student_id=student.id).order_by(WeightLog.log_date.asc()).first()
        if first_weight:
            days_since_start = (get_jst_now().date() - first_weight.log_date).days
            start_weight = first_weight.weight
            weight_lost = start_weight - weight_log.weight
        else:
            days_since_start = 0
            start_weight = weight_log.weight
            weight_lost = 0

        # 達成度の計算
        progress_percentage = 0
        if student.target_weight and first_weight and student.target_weight != start_weight:
            progress = (start_weight - weight_log.weight) / (start_weight - student.target_weight)
            progress_percentage = max(0, min(100, progress * 100))

        display_data.append({
            'student_id': student.id,
            'nickname': student.nickname,
            'weight': weight_log.weight,
            'start_weight': start_weight,
            'weight_lost': weight_lost,
            'log_date': weight_log.log_date.strftime('%Y年%m月%d日'),
            'target_weight': student.target_weight,
            'target_info': target_info,
            'target_status': target_status,
            'days_since_start': days_since_start,
            'progress_percentage': round(progress_percentage, 1),
            'remaining_weight': diff_abs if student.target_weight else 0
        })
    
    return render_template('home.html', 
                           nickname_to_display=current_nickname,
                           public_weight_data=display_data)

# ===== 生徒認証関連 =====
@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        height_str = request.form.get('height')
        age_group = request.form.get('age_group')

        if not nickname or not email or not password or not confirm_password:
            flash('必須項目をすべて入力してください。', 'danger')
            return redirect(url_for('register_page'))
        if password != confirm_password:
            flash('パスワードが一致しません。', 'danger')
            return redirect(url_for('register_page'))
        
        existing_student = Student.query.filter_by(email=email).first()
        if existing_student:
            flash('そのメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('register_page'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        height = float(height_str) if height_str else None
        
        new_student = Student(
            nickname=nickname, 
            email=email, 
            password_hash=hashed_password, 
            height=height, 
            age_group=age_group, 
            is_public_weight=False, 
            target_weight=None
        )
        db.session.add(new_student)
        db.session.commit()
        
        flash(f'ようこそ、{nickname}さん！登録が完了しました。', 'success')
        return redirect(url_for('home'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('メールアドレスとパスワードを入力してください。', 'danger')
            return redirect(url_for('login_page'))
        
        student = Student.query.filter_by(email=email).first()
        if student and check_password_hash(student.password_hash, password):
            session['student_id'] = student.id
            session['nickname'] = student.nickname
            flash(f'こんにちは、{student.nickname}さん！', 'success')
            return redirect(url_for('dashboard_page'))
        else:
            flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
            return redirect(url_for('login_page'))
            
    return render_template('login.html')

@app.route('/logout')
def logout_user():
    session.pop('student_id', None)
    session.pop('nickname', None)
    flash('ログアウトしました。', 'success')
    return redirect(url_for('home'))

# ===== 生徒ダッシュボード =====
@app.route('/dashboard')
def dashboard_page():
    if 'student_id' not in session:
        flash('ダッシュボードにアクセスするにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    current_student_id = session['student_id']
    current_nickname = session.get('nickname')
    
    current_student = Student.query.get(current_student_id)
    if not current_student:
        flash('生徒情報が見つかりません。', 'danger')
        return redirect(url_for('login_page'))
    
    # 選択された日付の取得
    selected_date_str = request.args.get('selected_date')
    if selected_date_str:
        try:
            default_date_to_use = datetime.fromisoformat(selected_date_str).date()
        except ValueError:
            default_date_to_use = get_jst_now().date()
    else:
        default_date_to_use = get_jst_now().date()

    # 体重履歴のページング処理
    weight_page = request.args.get('weight_page', 1, type=int)
    per_page = 10

    weight_logs_paginated = WeightLog.query.filter_by(
        student_id=current_student_id
    ).order_by(WeightLog.log_date.desc()).paginate(
        page=weight_page,
        per_page=per_page,
        error_out=False
    )

    # その日のデータを取得
    daily_sleep_logs = SleepLog.query.filter_by(
        student_id=current_student_id, 
        log_date=default_date_to_use
    ).order_by(SleepLog.log_date.desc()).all()

    daily_bm_logs = BowelMovementLog.query.filter_by(
        student_id=current_student_id,
        log_date=default_date_to_use
    ).order_by(BowelMovementLog.log_date.desc()).all()

    daily_weight_logs = WeightLog.query.filter_by(
        student_id=current_student_id,
        log_date=default_date_to_use
    ).order_by(WeightLog.log_date.desc()).all()

    daily_meal_logs = MealLog.query.filter(
        MealLog.student_id == current_student_id,
        db.func.date(MealLog.meal_datetime) == default_date_to_use
    ).order_by(MealLog.meal_datetime.desc()).all()
    
    daily_summary = {
        'sleep': daily_sleep_logs,
        'bowel_movement': daily_bm_logs,
        'weight': daily_weight_logs,
        'meal': daily_meal_logs
    }

    # カロリー合計を計算
    total_daily_calories = 0
    for meal in daily_meal_logs:
        if meal.total_calories:
            total_daily_calories += meal.total_calories

    # 最近の食事記録
    recent_meal_logs = MealLog.query.filter_by(
        student_id=current_student_id
    ).order_by(MealLog.meal_datetime.desc()).limit(20).all()

    # 現在の体重と目標進捗を計算
    current_weight = None
    if daily_weight_logs:
        current_weight = daily_weight_logs[0].weight
    elif current_student.weight_logs:
        latest_weight = WeightLog.query.filter(
            WeightLog.student_id == current_student_id
        ).order_by(WeightLog.log_date.desc()).first()
        if latest_weight:
            current_weight = latest_weight.weight

    target_progress_info = None
    if current_student.target_weight is not None and current_weight is not None:
        diff_abs = abs(current_weight - current_student.target_weight)
        if current_weight > current_student.target_weight:
            target_progress_info = f"目標: {current_student.target_weight:.1f}kg (あと {diff_abs:.1f}kg 減)"
        elif current_weight < current_student.target_weight:
            target_progress_info = f"目標: {current_student.target_weight:.1f}kg (あと {diff_abs:.1f}kg 増)"
        else:
            target_progress_info = f"目標: {current_student.target_weight:.1f}kg (🎉 達成！)"

    # 未読メッセージ数を取得
    unread_message_count = Message.query.filter_by(
        student_id=current_student_id,
        receiver_type='student',
        receiver_id=current_student_id,
        is_read=False,
        is_deleted=False
    ).count()

    return render_template('dashboard.html', 
                           nickname_to_display=current_nickname, 
                           default_date=default_date_to_use,
                           daily_summary_logs=daily_summary,
                           weight_logs_paginated=weight_logs_paginated.items,
                           weight_pagination=weight_logs_paginated,
                           recent_meal_logs=recent_meal_logs,
                           total_daily_calories=total_daily_calories,
                           current_student=current_student,
                           target_progress_info=target_progress_info,
                           current_time=get_jst_now(),
                           unread_message_count=unread_message_count)

# ===== データ記録機能 =====
@app.route('/log_weight', methods=['POST'])
def log_weight_data():
    if 'student_id' not in session:
        flash('記録するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_date_str = request.form.get('weight_date')
    weight_str = request.form.get('weight_kg')
    body_fat_str = request.form.get('body_fat_percentage')
    
    if not log_date_str or not weight_str:
        flash('日付と体重を入力してください。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    try:
        log_date_obj = datetime.fromisoformat(log_date_str).date()
        weight = float(weight_str)
        if weight <= 0:
            flash('体重は0より大きい値を入力してください。', 'danger')
            return redirect(url_for('dashboard_page', selected_date=log_date_str))
        
        body_fat_percentage = None
        if body_fat_str:
            body_fat_percentage = float(body_fat_str)
            if body_fat_percentage < 0 or body_fat_percentage >= 100:
                flash('体脂肪率は0から100未満の値を入力してください。', 'danger')
                return redirect(url_for('dashboard_page', selected_date=log_date_str))
                 
    except ValueError:
        flash('体重または体脂肪率の入力値が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    new_weight_log = WeightLog(
        log_date=log_date_obj, 
        weight=weight, 
        body_fat_percentage=body_fat_percentage, 
        student_id=session['student_id']
    )
    db.session.add(new_weight_log)
    db.session.commit()
    
    flash('体重・体脂肪率を記録しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_date_str))

@app.route('/log_meal', methods=['POST'])
def log_meal_data():
    if 'student_id' not in session:
        flash('記録するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    date_str = request.form.get('meal_date')
    meal_type = request.form.get('meal_type')
    description = request.form.get('meal_description')
    calories_str = request.form.get('total_calories')
    
    if not date_str or not meal_type:
        flash('日付と食事タイプを選択してください。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=date_str or get_jst_now().date().isoformat()))
    
    # 食事タイプのバリデーション
    valid_meal_types = ['morning', 'lunch', 'dinner', 'snack1', 'snack2', 'snack3']
    if meal_type not in valid_meal_types:
        flash('正しい食事タイプを選択してください。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=date_str))
    
    try:
        meal_date_obj = datetime.fromisoformat(date_str).date()
        current_time = get_jst_now().time()
        meal_datetime_obj = datetime.combine(meal_date_obj, current_time)
        
        total_calories = None
        if calories_str:
            total_calories = int(calories_str)
            if total_calories < 0:
                flash('カロリーは0以上の値を入力してください。', 'danger')
                return redirect(url_for('dashboard_page', selected_date=date_str))
                
    except ValueError:
        flash('日付またはカロリーの入力形式が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=date_str or get_jst_now().date().isoformat()))
    
    new_meal_log = MealLog(
        meal_datetime=meal_datetime_obj, 
        meal_type=meal_type,
        description=description, 
        total_calories=total_calories, 
        student_id=session['student_id']
    )
    db.session.add(new_meal_log)
    db.session.commit()
    
    flash('食事を記録しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=date_str))

@app.route('/log_bowel_movement', methods=['POST'])
def log_bowel_movement_data():
    if 'student_id' not in session:
        flash('記録するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_date_str = request.form.get('bowel_date')
    occurred_str = request.form.get('bowel_occurred')
    
    if not log_date_str or occurred_str is None:
        flash('日付と排泄の有無を選択してください。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    try:
        log_date_obj = datetime.fromisoformat(log_date_str).date()
        occurred_bool = occurred_str == 'true'
    except ValueError:
        flash('日付の形式が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    new_bm_log = BowelMovementLog(
        log_date=log_date_obj, 
        occurred=occurred_bool, 
        student_id=session['student_id']
    )
    db.session.add(new_bm_log)
    db.session.commit()
    
    flash('排泄記録をしました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_date_str))

@app.route('/log_sleep', methods=['POST'])
def log_sleep_data():
    if 'student_id' not in session:
        flash('記録するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_date_str = request.form.get('sleep_date')
    duration_str = request.form.get('sleep_duration')
    
    if not log_date_str or not duration_str:
        flash('日付と睡眠時間を入力してください。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    try:
        log_date_obj = datetime.fromisoformat(log_date_str).date()
        duration = float(duration_str)
        if duration <= 0 or duration > 24:
            flash('睡眠時間は0より大きく24以下の値を入力してください。', 'danger')
            return redirect(url_for('dashboard_page', selected_date=log_date_str))
    except ValueError:
        flash('入力値が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page', selected_date=log_date_str or get_jst_now().date().isoformat()))
    
    new_sleep_log = SleepLog(log_date=log_date_obj, duration=duration, student_id=session['student_id'])
    db.session.add(new_sleep_log)
    db.session.commit()
    
    flash('睡眠時間を記録しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_date_str))

# ===== 設定更新 =====
@app.route('/update_target_weight', methods=['POST'])
def update_target_weight():
    if 'student_id' not in session:
        flash('目標体重を設定するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    current_student_id = session['student_id']
    student = Student.query.get(current_student_id)
    
    if not student:
        flash('生徒情報が見つかりません。', 'danger')
        return redirect(url_for('dashboard_page'))
            
    target_weight_str = request.form.get('target_weight')
    
    if target_weight_str:
        try:
            target_weight = float(target_weight_str)
            if target_weight <= 0:
                flash('目標体重は0より大きい値を入力してください。', 'danger')
                return redirect(url_for('dashboard_page'))
            student.target_weight = target_weight
            flash('目標体重を更新しました！', 'success')
        except ValueError:
            flash('目標体重の入力値が正しくありません。', 'danger')
    else:
        student.target_weight = None
        flash('目標体重をクリアしました。', 'success')
        
    db.session.commit()
    return redirect(url_for('dashboard_page'))

@app.route('/update_public_weight_setting', methods=['POST'])
def update_public_weight_setting():
    if 'student_id' not in session:
        flash('設定を更新するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    current_student_id = session['student_id']
    student = Student.query.get(current_student_id)
    
    if not student:
        flash('生徒情報が見つかりません。', 'danger')
        return redirect(url_for('dashboard_page'))
            
    is_public = request.form.get('is_public_weight') == 'true'
    
    student.is_public_weight = is_public
    db.session.commit()
    
    flash('体重公開設定を更新しました。', 'success')
    return redirect(url_for('dashboard_page'))

# ===== API エンドポイント =====
@app.route('/get_weight_data')
def get_weight_data():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_student_id = session['student_id']
    weight_logs = WeightLog.query.filter_by(student_id=current_student_id).order_by(WeightLog.log_date.asc()).all()
    
    dates = [log.log_date.strftime('%Y-%m-%d') for log in weight_logs]
    weights = [log.weight for log in weight_logs]
    
    return jsonify({
        'labels': dates,
        'data': weights
    })

@app.route('/get_public_weight_data/<int:student_id>')
def get_public_weight_data(student_id):
    student = Student.query.get(student_id)
    if not student or not student.is_public_weight:
        return jsonify({'error': 'Unauthorized or not public'}), 403

    weight_logs = WeightLog.query.filter_by(student_id=student_id).order_by(WeightLog.log_date.asc()).all()
    
    dates = [log.log_date.strftime('%Y-%m-%d') for log in weight_logs]
    weights = [log.weight for log in weight_logs]
    
    return jsonify({
        'labels': dates,
        'data': weights,
        'nickname': student.nickname
    })

# ===== トレーナー機能 =====
@app.route('/trainer_register', methods=['GET', 'POST'])
def trainer_register_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not name or not email or not password or not confirm_password:
            flash('すべての必須項目を入力してください。', 'danger')
            return redirect(url_for('trainer_register_page'))

        if password != confirm_password:
            flash('パスワードが一致しません。', 'danger')
            return redirect(url_for('trainer_register_page'))

        existing_trainer = Trainer.query.filter_by(email=email).first()
        if existing_trainer:
            flash('そのメールアドレスは既にトレーナーとして登録されています。', 'danger')
            return redirect(url_for('trainer_register_page'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_trainer = Trainer(name=name, email=email, password_hash=hashed_password)
        
        db.session.add(new_trainer)
        db.session.commit()
        flash(f'トレーナーの{name}さん、登録が完了しました！ログインしてください。', 'success')
        return redirect(url_for('trainer_login_page'))
    
    return render_template('trainer_register.html')

@app.route('/trainer_login', methods=['GET', 'POST'])
def trainer_login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('メールアドレスとパスワードを入力してください。', 'danger')
            return redirect(url_for('trainer_login_page'))
        
        trainer = Trainer.query.filter_by(email=email).first()
        if trainer and check_password_hash(trainer.password_hash, password):
            session['trainer_id'] = trainer.id
            session['trainer_name'] = trainer.name
            flash(f'こんにちは、{trainer.name}トレーナー！', 'success')
            return redirect(url_for('trainer_dashboard_page'))
        else:
            flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
            return redirect(url_for('trainer_login_page'))
            
    return render_template('trainer_login.html')

@app.route('/trainer_logout')
def trainer_logout():
    session.pop('trainer_id', None)
    session.pop('trainer_name', None)
    flash('トレーナーアカウントからログアウトしました。', 'success')
    return redirect(url_for('home'))

@app.route('/trainer_dashboard')
def trainer_dashboard_page():
    if 'trainer_id' not in session:
        flash('トレーナーダッシュボードにアクセスするにはログインが必要です。', 'danger')
        return redirect(url_for('trainer_login_page'))
    
    # 全生徒を取得し、最新の体重データも含める
    students_with_latest_weight = []
    all_students = Student.query.order_by(Student.nickname).all()
    
    for student in all_students:
        latest_weight_log = WeightLog.query.filter_by(student_id=student.id).order_by(WeightLog.log_date.desc()).first()
        latest_meal_log = MealLog.query.filter_by(student_id=student.id).order_by(MealLog.meal_datetime.desc()).first()
        
        students_with_latest_weight.append({
            'student': student,
            'latest_weight': latest_weight_log.weight if latest_weight_log else None,
            'latest_weight_date': latest_weight_log.log_date if latest_weight_log else None,
            'latest_meal_date': latest_meal_log.meal_datetime.date() if latest_meal_log else None,
            'total_logs': len(student.weight_logs) + len(student.meal_logs) + len(student.sleep_logs)
        })

    return render_template('trainer_dashboard.html', 
                           trainer_name=session.get('trainer_name'),
                           students_data=students_with_latest_weight,
                           current_date=get_jst_now().date())

@app.route('/trainer/student/<int:student_id>')
def trainer_student_detail(student_id):
    if 'trainer_id' not in session:
        flash('生徒の詳細にアクセスするにはトレーナーとしてログインが必要です。', 'danger')
        return redirect(url_for('trainer_login_page'))
    
    student = Student.query.options(
        joinedload(Student.sleep_logs),
        joinedload(Student.bowel_movement_logs),
        joinedload(Student.weight_logs),
        joinedload(Student.meal_logs)
    ).get_or_404(student_id)
    
    # 過去30日間のデータを取得
    thirty_days_ago = get_jst_now().date() - timedelta(days=30)
    
    recent_weight_logs = WeightLog.query.filter(
        WeightLog.student_id == student_id,
        WeightLog.log_date >= thirty_days_ago
    ).order_by(WeightLog.log_date.desc()).all()
    
    recent_meal_logs = MealLog.query.filter(
        MealLog.student_id == student_id,
        MealLog.meal_datetime >= datetime.combine(thirty_days_ago, datetime.min.time())
    ).order_by(MealLog.meal_datetime.desc()).all()

    return render_template('trainer_student_detail.html', 
                           student=student,
                           recent_weight_logs=recent_weight_logs,
                           recent_meal_logs=recent_meal_logs,
                           trainer_name=session.get('trainer_name'))

# ===== 埋め込み用グラフAPI =====
@app.route('/embed/weight_chart/<int:student_id>')
def embed_weight_chart(student_id):
    """ホームページ埋め込み用の体重チャート"""
    student = Student.query.get(student_id)
    if not student or not student.is_public_weight:
        return "データが公開されていません", 403
    
    return render_template('embed_weight_chart.html', 
                           student_id=student_id,
                           student_nickname=student.nickname)

# ===== メッセージ関連のルート =====


# app.pyのmessages_pageルートを修正

@app.route('/messages')
def messages_page():
    """メッセージ一覧ページ（生徒用）"""
    if 'student_id' not in session:
        flash('メッセージを見るにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    current_student_id = session['student_id']
    current_student = Student.query.get(current_student_id)
    
    # この生徒に関連する削除されていないメッセージを取得（古い順）
    messages = Message.query.filter_by(
        student_id=current_student_id,
        is_deleted=False
    ).order_by(Message.created_at.asc()).all()  # asc()で古い順に変更
    
    # 未読メッセージを既読にする
    unread_messages = Message.query.filter_by(
        student_id=current_student_id,
        receiver_type='student',
        receiver_id=current_student_id,
        is_read=False,
        is_deleted=False
    ).all()
    
    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()
    
    # トレーナー情報を取得
    trainer_ids = list(set([msg.trainer_id for msg in messages]))
    trainers = {t.id: t for t in Trainer.query.filter(Trainer.id.in_(trainer_ids)).all()}
    
    return render_template('messages.html', 
                         messages=messages, 
                         trainers=trainers,
                         current_student=current_student,
                         current_time=get_jst_now())

@app.route('/trainer/messages/<int:student_id>')
def trainer_messages_page(student_id):
    """トレーナー用メッセージページ"""
    if 'trainer_id' not in session:
        flash('メッセージを見るにはトレーナーとしてログインが必要です。', 'danger')
        return redirect(url_for('trainer_login_page'))
    
    current_trainer_id = session['trainer_id']
    current_trainer = Trainer.query.get(current_trainer_id)
    student = Student.query.get_or_404(student_id)
    
    # この生徒とトレーナー間の削除されていないメッセージを取得
    messages = Message.query.filter_by(
        student_id=student_id,
        trainer_id=current_trainer_id,
        is_deleted=False
    ).order_by(Message.created_at.asc()).all()
    
    # 未読メッセージを既読にする
    unread_messages = Message.query.filter_by(
        student_id=student_id,
        trainer_id=current_trainer_id,
        receiver_type='trainer',
        receiver_id=current_trainer_id,
        is_read=False,
        is_deleted=False
    ).all()
    
    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()
    
    return render_template('trainer_messages.html', 
                         messages=messages, 
                         student=student,
                         current_trainer=current_trainer,
                         current_time=get_jst_now())


# app.pyのsend_messageルートを修正

@app.route('/send_message', methods=['POST'])
def send_message():
    """メッセージ送信（生徒用）"""
    if 'student_id' not in session:
        flash('メッセージを送信するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    current_student_id = session['student_id']
    trainer_id = request.form.get('trainer_id')
    content = request.form.get('content')
    message_type = request.form.get('message_type', 'general')
    
    # ファイルアップロード処理
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = get_jst_now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}.jpg"  # 圧縮後はJPEGで保存
            
            if save_compressed_image(file, unique_filename):
                image_filename = unique_filename
            else:
                flash('画像のアップロードに失敗しました。', 'danger')
    
    if not trainer_id or not content.strip():
        flash('トレーナーとメッセージ内容を入力してください。', 'danger')
        return redirect(url_for('messages_page'))
    
    trainer = Trainer.query.get(trainer_id)
    if not trainer:
        flash('指定されたトレーナーが見つかりません。', 'danger')
        return redirect(url_for('messages_page'))
    
    new_message = Message(
        sender_type='student',
        sender_id=current_student_id,
        receiver_type='trainer',
        receiver_id=trainer_id,
        student_id=current_student_id,
        trainer_id=trainer_id,
        content=content.strip(),
        message_type=message_type,
        image_filename=image_filename,
        created_at=get_jst_now().replace(tzinfo=None)  # タイムゾーンなしで保存
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    flash('メッセージを送信しました！', 'success')
    # スクロール用パラメータを追加してリダイレクト
    return redirect(url_for('messages_page', sent='true'))

@app.route('/trainer/send_message', methods=['POST'])
def trainer_send_message():
    """メッセージ送信（トレーナー用）"""
    if 'trainer_id' not in session:
        flash('メッセージを送信するにはトレーナーとしてログインが必要です。', 'danger')
        return redirect(url_for('trainer_login_page'))
    
    current_trainer_id = session['trainer_id']
    student_id = request.form.get('student_id')
    content = request.form.get('content')
    message_type = request.form.get('message_type', 'advice')
    
    # ファイルアップロード処理
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = get_jst_now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}.jpg"  # 圧縮後はJPEGで保存
            
            if save_compressed_image(file, unique_filename):
                image_filename = unique_filename
            else:
                flash('画像のアップロードに失敗しました。', 'danger')
    
    if not student_id or not content.strip():
        flash('生徒とメッセージ内容を入力してください。', 'danger')
        return redirect(url_for('trainer_dashboard_page'))
    
    student = Student.query.get(student_id)
    if not student:
        flash('指定された生徒が見つかりません。', 'danger')
        return redirect(url_for('trainer_dashboard_page'))
    
    new_message = Message(
        sender_type='trainer',
        sender_id=current_trainer_id,
        receiver_type='student',
        receiver_id=student_id,
        student_id=student_id,
        trainer_id=current_trainer_id,
        content=content.strip(),
        message_type=message_type,
        image_filename=image_filename,
        created_at=get_jst_now()
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    flash('メッセージを送信しました！', 'success')
    return redirect(url_for('trainer_messages_page', student_id=student_id))

@app.route('/get_unread_count')
def get_unread_count():
    """未読メッセージ数を取得（生徒用）"""
    if 'student_id' not in session:
        return jsonify({'count': 0})
    
    current_student_id = session['student_id']
    unread_count = Message.query.filter_by(
        student_id=current_student_id,
        receiver_type='student',
        receiver_id=current_student_id,
        is_read=False,
        is_deleted=False
    ).count()
    
    return jsonify({'count': unread_count})

@app.route('/trainer/get_unread_count/<int:student_id>')
def trainer_get_unread_count(student_id):
    """未読メッセージ数を取得（トレーナー用）"""
    if 'trainer_id' not in session:
        return jsonify({'count': 0})
    
    current_trainer_id = session['trainer_id']
    unread_count = Message.query.filter_by(
        student_id=student_id,
        trainer_id=current_trainer_id,
        receiver_type='trainer',
        receiver_id=current_trainer_id,
        is_read=False,
        is_deleted=False
    ).count()
    
    return jsonify({'count': unread_count})

# ===== メッセージ削除機能 =====
@app.route('/api/messages/<int:message_id>/delete', methods=['POST'])
def delete_message(message_id):
    try:
        # セッション確認
        if 'student_id' not in session and 'trainer_id' not in session:
            return jsonify({"success": False, "error": "認証が必要です"}), 401
        
        # メッセージ取得
        message = Message.query.get_or_404(message_id)
        
        # 権限チェック
        can_delete = False
        
        if 'student_id' in session:
            if message.sender_type == 'student' and message.student_id == session['student_id']:
                can_delete = True
        
        if 'trainer_id' in session:
            if message.sender_type == 'trainer' and message.trainer_id == session['trainer_id']:
                can_delete = True
        
        if not can_delete:
            return jsonify({"success": False, "error": "このメッセージを削除する権限がありません"}), 403
        
        # 取り消し処理
        message.is_recalled = True
        message.recalled_by = 'student' if 'student_id' in session else 'trainer'
        message.recalled_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "メッセージを取り消しました"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ===== ファイルアップロード関連 =====
@app.route('/uploads/messages/<filename>')
def uploaded_file(filename):
    """アップロードされた画像を表示"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ===== 更新用ルート =====
@app.route('/update_weight_log/<int:log_id>', methods=['POST'])
def update_weight_log(log_id):
    if 'student_id' not in session:
        flash('記録を更新するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_to_update = WeightLog.query.get_or_404(log_id)
    if log_to_update.student_id != session['student_id']:
        flash('権限がありません。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    weight_str = request.form.get('weight_kg')
    body_fat_str = request.form.get('body_fat_percentage')
    
    if not weight_str:
        flash('体重を入力してください。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    try:
        weight = float(weight_str)
        if weight <= 0:
            flash('体重は0より大きい値を入力してください。', 'danger')
            return redirect(url_for('dashboard_page'))
        
        body_fat_percentage = None
        if body_fat_str:
            body_fat_percentage = float(body_fat_str)
            if body_fat_percentage < 0 or body_fat_percentage >= 100:
                flash('体脂肪率は0から100未満の値を入力してください。', 'danger')
                return redirect(url_for('dashboard_page'))
                
    except ValueError:
        flash('体重または体脂肪率の入力値が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    log_to_update.weight = weight
    log_to_update.body_fat_percentage = body_fat_percentage
    db.session.commit()
    
    flash('体重記録を更新しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_to_update.log_date.isoformat()))

@app.route('/update_bowel_log/<int:log_id>', methods=['POST'])
def update_bowel_log(log_id):
    if 'student_id' not in session:
        flash('記録を更新するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_to_update = BowelMovementLog.query.get_or_404(log_id)
    if log_to_update.student_id != session['student_id']:
        flash('権限がありません。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    occurred_str = request.form.get('bowel_occurred')
    if occurred_str is None:
        flash('選択肢を選んでください。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    occurred_bool = occurred_str == 'true'
    log_to_update.occurred = occurred_bool
    db.session.commit()
    
    flash('排泄記録を更新しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_to_update.log_date.isoformat()))

@app.route('/update_meal_log/<int:log_id>', methods=['POST'])
def update_meal_log(log_id):
    if 'student_id' not in session:
        flash('記録を更新するにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_to_update = MealLog.query.get_or_404(log_id)
    if log_to_update.student_id != session['student_id']:
        flash('権限がありません。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    meal_date_str = request.form.get('meal_date')
    meal_type = request.form.get('meal_type')
    description = request.form.get('meal_description')
    calories_str = request.form.get('total_calories')
    
    if not meal_date_str or not meal_type:
        flash('日付と食事タイプを選択してください。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    valid_meal_types = ['morning', 'lunch', 'dinner', 'snack1', 'snack2', 'snack3']
    if meal_type not in valid_meal_types:
        flash('正しい食事タイプを選択してください。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    try:
        meal_date_obj = datetime.fromisoformat(meal_date_str).date()
        current_time = get_jst_now().time()
        meal_datetime_obj = datetime.combine(meal_date_obj, current_time)
        
        total_calories = None
        if calories_str:
            total_calories = int(calories_str)
            if total_calories < 0:
                flash('カロリーは0以上の値を入力してください。', 'danger')
                return redirect(url_for('dashboard_page'))
                
    except ValueError:
        flash('日付またはカロリーの入力形式が正しくありません。', 'danger')
        return redirect(url_for('dashboard_page'))
    
    log_to_update.meal_datetime = meal_datetime_obj
    log_to_update.meal_type = meal_type
    log_to_update.description = description
    log_to_update.total_calories = total_calories
    db.session.commit()
    
    flash('食事記録を更新しました！', 'success')
    return redirect(url_for('dashboard_page', selected_date=meal_date_str))

# ===== 削除用ルート =====
@app.route('/delete_sleep_log/<int:log_id>', methods=['POST'])
def delete_sleep_log(log_id):
    if 'student_id' not in session:
        flash('操作を行うにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_to_delete = SleepLog.query.get_or_404(log_id)
    if log_to_delete.student_id != session['student_id']:
        flash('権限がありません。', 'danger')
        return redirect(url_for('dashboard_page'))
        
    log_date_str = log_to_delete.log_date.isoformat()
    db.session.delete(log_to_delete)
    db.session.commit()
    
    flash('睡眠記録を削除しました。', 'success')
    return redirect(url_for('dashboard_page', selected_date=log_date_str))

@app.route('/delete_bowel_log/<int:log_id>', methods=['POST'])
def delete_bowel_log(log_id):
    if 'student_id' not in session:
        flash('操作を行うにはログインが必要です。', 'danger')
        return redirect(url_for('login_page'))
    
    log_to_delete = BowelMovementLog.query.get_or_404(log_id)
    if log_to_delete.student_id != session['student_id']:
        flash('権限がありません。', 'danger')
        return redirect(url_for('dashboard_page'))
        
    log_date_str = log_to_delete.log_date.isoformat()
    db.session.delete(log_to_delete)
    db.session.commit()

    # ===== アプリケーション実行部分 =====
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # データベーステーブルを作成
    app.run(debug=True, host='0.0.0.0', port=5000)

    # app.pyに追加するリアルタイムメッセージAPI

# app.pyに追加するシンプルなリアルタイムメッセージAPI

@app.route('/api/messages/new')
def get_new_messages():
    try:
        after_id = int(request.args.get('after', 0))
        check_recalled = request.args.get('check_recalled', 'false').lower() == 'true'
        student_id = request.args.get('student_id')  # トレーナー用
        
        # 現在のユーザーIDを取得
        if 'trainer_id' in session:
            # トレーナーの場合
            current_trainer_id = session['trainer_id']
            if student_id:
                messages_query = Message.query.filter(
                    Message.id > after_id,
                    or_(
                        and_(Message.student_id == student_id, Message.trainer_id == current_trainer_id),
                        and_(Message.student_id == student_id, Message.sender_type == 'student')
                    )
                ).order_by(Message.created_at.asc())
            else:
                return jsonify({"success": False, "error": "student_id required"})
        else:
            # 生徒の場合
            current_student_id = session['student_id']
            messages_query = Message.query.filter(
                Message.id > after_id,
                Message.student_id == current_student_id
            ).order_by(Message.created_at.asc())
            student_id = current_student_id

        new_messages = messages_query.all()
        
        response = {
            "success": True,
            "messages": [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "sender_type": msg.sender_type,
                    "message_type": msg.message_type,
                    "image_filename": msg.image_filename,
                    "created_at": msg.created_at.isoformat(),
                    "is_recalled": getattr(msg, 'is_recalled', False),
                    "recalled_by": getattr(msg, 'recalled_by', None)
                }
                for msg in new_messages if not getattr(msg, 'is_recalled', False)
            ],
            "recalled_messages": [],
            "deleted_messages": []
        }
        
        # 取り消し状態チェック
        if check_recalled:
            if 'trainer_id' in session:
                all_messages = Message.query.filter(
                    or_(
                        and_(Message.student_id == student_id, Message.trainer_id == current_trainer_id),
                        and_(Message.student_id == student_id, Message.sender_type == 'student')
                    )
                ).all()
            else:
                all_messages = Message.query.filter(
                    Message.student_id == current_student_id
                ).all()
            
            response["all_messages"] = [
                {
                    "id": msg.id,
                    "is_recalled": getattr(msg, 'is_recalled', False),
                    "recalled_by": getattr(msg, 'recalled_by', None)
                }
                for msg in all_messages
            ]
            
            recently_recalled = [
                msg.id for msg in all_messages 
                if getattr(msg, 'is_recalled', False) and msg.id > after_id
            ]
            response["recalled_messages"] = recently_recalled
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
