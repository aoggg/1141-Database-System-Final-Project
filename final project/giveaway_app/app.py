from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") # 這邊可以隨便放一個字串，寫在 .env 裡面

# 這裡設定資料庫
DB_HOST = "localhost"
DB_NAME = "aogDB"  # 資料庫的名稱
DB_USER = "postgres"  # 使用者帳號，預設應該都是 postgres
DB_PASS = os.getenv("DB_PASSWORD")   # 設定的密碼，寫在 .env 裡面
DB_PORT = "5432"

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn

@app.route('/')
def index():
    # 1. 處理視圖模式
    url_view = request.args.get('view')
    if url_view:
        session['saved_view_mode'] = url_view
        view_mode = url_view
    else:
        view_mode = session.get('saved_view_mode', 'post')

    category_filter = request.args.get('category')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    user_id = session.get('user_id')

    cur.execute("SELECT * FROM categories ORDER BY category_id ASC")
    all_categories = cur.fetchall()

    if view_mode == 'item':
        cnt_sql = """
        SELECT sum(i.quantity)
        FROM item i
        JOIN post p ON i.post_id = p.post_id
        LEFT JOIN categories c ON i.category_id = c.category_id
        WHERE i.quantity > 0
        """
        cnt_params = []

        if user_id:
            cnt_sql += " AND p.user_id != %s"
            cnt_params.append(user_id)
        
        if category_filter:
            cnt_sql += " AND c.category_id = %s"
            cnt_params.append(category_filter)

        cur.execute(cnt_sql, tuple(cnt_params))
        result = cur.fetchone()
        cnt = result[0] if result and result[0] else 0

        sql = """
        SELECT i.item_id, i.item_name, i.quantity, i.expiration_date,
               c.name, c.category_id,
               p.description, p.available, 
               l.location_name, l.city, l.district, l.street, l.number,
               u.name as user_name, u.user_id
        FROM item i 
        LEFT JOIN post p ON i.post_id = p.post_id
        LEFT JOIN location l ON i.location_id = l.location_id
        LEFT JOIN categories c ON i.category_id = c.category_id
        LEFT JOIN users u ON p.user_id = u.user_id
        WHERE i.quantity > 0
        """
        query_params = []

        if user_id:
            sql += " AND p.user_id != %s"
            query_params.append(user_id)

        if category_filter:
            sql += " AND c.category_id = %s"
            query_params.append(category_filter)

        sql += """
        ORDER BY i.quantity DESC,
                 p.post_id DESC,
                 c.category_id ASC
        """
        cur.execute(sql, tuple(query_params))
        items = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('index_item.html', 
                               view_mode='item', 
                               items=items, 
                               total=cnt,
                               categories=all_categories,
                               current_category=category_filter)
    
    else:
        sql = """
        SELECT i.item_id, i.item_name, i.quantity, i.expiration_date,
               c.name, c.category_id,
               p.description, p.available, p.post_id,
               l.location_name, l.city, l.district, l.street, l.number,
               u.name as user_name, u.user_id
        FROM item i
        LEFT JOIN post p ON i.post_id = p.post_id
        LEFT JOIN location l ON i.location_id = l.location_id
        LEFT JOIN categories c ON i.category_id = c.category_id
        LEFT JOIN users u ON p.user_id = u.user_id
        WHERE p.available = TRUE
        """
        query_params = []

        if user_id:
            sql += " AND p.user_id != %s"
            query_params.append(user_id)

        if category_filter:
            sql += " AND c.category_id = %s"
            query_params.append(category_filter)

        sql += """
        ORDER BY p.post_id DESC,
            c.category_id ASC
        """

        cur.execute(sql, tuple(query_params))
        data = cur.fetchall()
        cur.close()
        conn.close()

        posts_map = {}

        for i in data:
            p_id = i['post_id']
            if p_id not in posts_map:
                posts_map[p_id] = {
                    'post_id': p_id,
                    'description': i['description'],
                    'available': i['available'],
                    'items': [],
                    'owner_name': i['user_name'],
                    'owner_id': i['user_id']
                }

            item_data = {
                'item_id': i['item_id'],
                'item_name': i['item_name'],
                'quantity': i['quantity'],
                'expiration_date': i['expiration_date'],
                'location_name': i['location_name'],
                'city': i['city'],
                'district': i['district'],
                'street': i['street'],
                'number': i['number'],
                'category_name': i['name']
            }

            posts_map[p_id]['items'].append(item_data)
        
        total_posts = len(posts_map)

        return render_template('index_post.html', 
                               view_mode="post", 
                               posts=list(posts_map.values()),
                               total=total_posts,
                               categories=all_categories,
                               current_category=category_filter)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_input = request.form['username']
        password_input = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql = """
            SELECT a.user_id, a.pwd, u.name
            FROM (account a JOIN users u
                ON u.user_id = a.user_id)
            WHERE a.username = %s;
            """
            cur.execute(sql, (username_input,))
            account = cur.fetchone()

            if account:
                if check_password_hash(account['pwd'], password_input):
                    update_sql = """
                        UPDATE account
                        SET lastlogin = NOW()
                        WHERE user_id = %s;
                    """
                    cur.execute(update_sql, (account['user_id'],))
                    conn.commit()

                    session['user_id'] = account['user_id']
                    session['username'] = account['name']
                    flash('登入成功！')
                    return redirect(url_for('index'))
                else:
                    flash('密碼錯誤！')
            else:
                flash('帳戶名稱錯誤或帳戶不存在')
        except Exception as e:
            conn.rollback()
            print(f"登入過程發生錯誤: {e}")
            flash('系統錯誤，請稍後再試')

        finally:
            cur.close()
            conn.close()

    return render_template('login.html')    

@app.route('/logout')
def logout():
    session.clear()
    flash('成功登出')
    return redirect(url_for('index'))

@app.route('/claim/<int:item_id>', methods=['POST'])
def claim(item_id):
    if 'user_id' not in session:
        flash('請先登入！')
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    want_quantity = request.form.get('want_quantity', 1, type=int)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        find_item = """
            SELECT quantity, item_name
            FROM item
            WHERE item_id = %s;
        """

        cur.execute(find_item, (item_id,))
        item = cur.fetchone()

        if (item and want_quantity > 0 and item['quantity'] >= want_quantity):
            insert_trade = """
                INSERT INTO trade (user_id, item_id, quantity, trade_time)
                VALUES (%s, %s, %s, NOW());
            """
            cur.execute(insert_trade, (session['user_id'], item_id, want_quantity,))
            conn.commit()

            flash(f'索取成功！你拿到了 {want_quantity} 個 {item["item_name"]} 🎉')

        elif item and item['quantity'] < want_quantity:
            flash(f'庫存不夠！只有{item["quantity"]} 個！')

        else:
            flash('發生錯誤！請重新操作！')

    except Exception as e:
        conn.rollback()
        flash(f'交易失敗：{e}')

    finally:
        cur.close()
        conn.close()

    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    info_sql = """
    SELECT u.name, u.organization, a.username,
           COALESCE(AVG(c.rating), 0) as avg_score,
           COUNT(c.comment_id) as review_count
    FROM ((users u LEFT JOIN account a 
            ON u.user_id = a.user_id) LEFT JOIN post p 
            ON u.user_id = p.user_id) LEFT JOIN comment c 
            ON p.post_id = c.post_id
    WHERE u.user_id = %s
    GROUP BY u.user_id, a.username;
    """
    cur.execute(info_sql, (user_id,))
    user_info = cur.fetchone()

    phone_sql = """
    SELECT phone_number
    FROM phone
    WHERE user_id = %s
    """
    cur.execute(phone_sql, (user_id,))
    phone = cur.fetchall()

    comments_sql = """
    SELECT c.comment_str, c.rating, c.comment_time, p.description
    FROM (comment c LEFT JOIN post p
            ON c.post_id = p.post_id)
    WHERE p.user_id = %s
    ORDER BY c.comment_time DESC
    """
    cur.execute(comments_sql, (user_id,))
    past_comments = cur.fetchall()

    claim_sql = """
    SELECT t.trade_time, t.quantity, i.item_name, 
           p.description as post_title, p.post_id,
            (SELECT rating FROM comment c 
             WHERE c.post_id = p.post_id AND c.user_id = %s LIMIT 1) as my_rating
    FROM (trade t LEFT JOIN item i
             ON t.item_id = i.item_id) LEFT JOIN post p
             ON i.post_id = p.post_id
    WHERE t.user_id = %s
    ORDER BY t.trade_time DESC
    """
    cur.execute(claim_sql, (user_id, user_id))
    my_claims = cur.fetchall()


    post_sql = """
    SELECT p.post_id,  p.description, p.post_time, p.available,
           (SELECT COUNT(*) FROM item i WHERE i.post_id = p.post_id) as item_count
    FROM post p
    WHERE p.user_id = %s
    ORDER BY p.post_time DESC
    """
    cur.execute(post_sql, (user_id,))
    my_posts = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('profile.html', user=user_info, comments=past_comments, claims=my_claims, posts=my_posts, phones=phone)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT user_id FROM post WHERE post_id = %s", (post_id,))
        post = cur.fetchone()
        
        if post and post[0] == session['user_id']:
            cur.execute("DELETE FROM post WHERE post_id = %s", (post_id,))
            conn.commit()
            flash('貼文已刪除！')
        else:
            flash('你沒有權限刪除此貼文！')
            
    except Exception as e:
        conn.rollback()
        flash(f'刪除失敗: {e}')
        
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('profile'))

@app.route('/add_comment/<int:post_id>', methods=['GET', 'POST'])
def add_comment(post_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment_str = request.form.get('comment_str')

        if not rating or not comment_str:
            flash('請填寫分數與內容！')
            return redirect(url_for('add_comment', post_id=post_id))

        try:
            find_comment = """
            SELECT comment_id
            FROM comment
            WHERE post_id = %s and user_id = %s
            """
            cur.execute(find_comment, (post_id, user_id))
            
            if cur.fetchone():
                flash('你已經評價過這篇貼文囉！')
            else:
                # 寫入評價
                cur.execute("""
                    INSERT INTO comment (post_id, user_id, rating, comment_str)
                    VALUES (%s, %s, %s, %s)
                """, (post_id, user_id, rating, comment_str))
                conn.commit()
                flash('評價成功！')

        except Exception as e:
            conn.rollback()
            flash(f'評價失敗: {e}')
        
        finally:
            cur.close()
            conn.close()

        # 評價完，跳轉回個人頁面
        return redirect(url_for('profile'))

    # 3. 顯示表單 (GET)
    # 我們需要抓貼文標題，讓使用者知道他在評哪一篇
    post_sql = """
    SELECT description
    FROM post
    WHERE post_id = %s
    """
    cur.execute(post_sql, (post_id,))
    post = cur.fetchone()
    cur.close()
    conn.close()

    if not post:
        flash('找不到該貼文！')
        return redirect(url_for('index'))

    return render_template('add_comment.html', post=post, post_id=post_id)

@app.route('/edit_name', methods=['GET', 'POST'])
def edit_name():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        new_name = request.form.get('name')

        if not new_name:
            flash('要輸入名字！')
        else:
            try:
                update_sql = """
                UPDATE users
                SET name = %s
                WHERE user_id = %s
                """
                cur.execute(update_sql, (new_name, session['user_id']))
                conn.commit()
                flash('名字修改成功！')
                session['username'] = new_name
                return redirect(url_for('profile'))
            except Exception as e:
                conn.rollback()
                flash(f'修改失敗：{e}')
    cur.close()
    conn.close()
    return render_template('edit_name.html')

@app.route('/change_pwd', methods=['GET', 'POST'])
def change_pwd():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        old_pwd = request.form.get('old_pwd')
        new_pwd = request.form.get('new_pwd')
        confirm_pwd = request.form.get('confirm_pwd')

        conn = get_db_connection()
        cur = conn.cursor()

        pwd_sql = """
        SELECT pwd
        FROM account
        WHERE user_id = %s
        """

        cur.execute(pwd_sql, (session['user_id'],))
        result = cur.fetchone()

        if not result:
            flash('帳號異常，請重新登入')
            return redirect(url_for('login'))
        
        hash_pwd = result[0]

        if not check_password_hash(hash_pwd, old_pwd):
            flash('舊密碼錯誤！')
            cur.close()
            conn.close()
            return redirect(url_for('change_pwd'))
        
        if new_pwd != confirm_pwd:
            flash('兩次輸入的密碼不一樣！')
            cur.close()
            conn.close()
            return redirect(url_for('change_pwd'))
        
        new_hash = generate_password_hash(new_pwd)

        try:
            upd_sql = """
            UPDATE account
            SET pwd = %s
            WHERE user_id = %s
            """
            cur.execute(upd_sql, (new_hash, session['user_id']))
            conn.commit()
            flash('密碼修改成功！請重新登入！')

            session.clear()
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            flash(f'修改失敗：{e}')
            return redirect(url_for('change_pwd'))
        
        finally:
            cur.close()
            conn.close()

    return render_template('change_pwd.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        del_sql = """
        DELETE FROM users
        WHERE user_id = %s
        """
        cur.execute(del_sql, (session['user_id'],))
        conn.commit()

        session.clear()
        flash('帳號已刪除')
    
    except Exception as e:
        conn.rollback()
        flash(f'刪除失敗：{e}')
        return redirect(url_for('profile'))

    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        organization = request.form.get('organization')
        username = request.form.get('username')
        pwd = request.form.get('pwd')
        confirm_pwd = request.form.get('confirm_pwd')
        phone = request.form.get('phone')

        if not (name and username and pwd and confirm_pwd and phone):
            flash('請填寫所有必填欄位！')
            return redirect(url_for('register'))
        
        if pwd != confirm_pwd:
            flash('兩次密碼輸入不一樣！')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            check_username = """
            SELECT user_id
            FROM account
            WHERE username = %s
            """
            cur.execute(check_username, (username,))
            
            if cur.fetchone():
                flash('這個帳號已經被註冊過了！')
                return redirect(url_for('register'))
            
            check_phone = """
            SELECT phone_number
            FROM phone
            WHERE phone_number = %s
            """
            cur.execute(check_phone, (phone,))

            if cur.fetchone():
                flash('這支電話號碼已經被使用過了！')
                return redirect(url_for('register'))

            register_user = """
            INSERT INTO users (name, organization)
            VALUES (%s, %s)
            RETURNING user_id
            """
            cur.execute(register_user, (name, organization))
            new_user_id = cur.fetchone()[0]

            hash_pwd = generate_password_hash(pwd)

            register_account = """
            INSERT INTO account (user_id, username, pwd)
            VALUES (%s, %s, %s)
            """
            cur.execute(register_account, (new_user_id, username, hash_pwd))
            
            register_phone = """
            INSERT INTO phone (phone_number, user_id)
            VALUES (%s, %s) 
            """
            cur.execute(register_phone, (phone, new_user_id))

            conn.commit()
            flash('註冊成功！請登入')
            return redirect(url_for('login'))
        
        except Exception as e:
            conn.rollback()
            flash('註冊失敗：{e}')
            return redirect(url_for('register'))
        
        finally:
            cur.close()
            conn.close()

    return render_template('register.html')

@app.route('/user/<int:target_user_id>')
def public_profile(target_user_id):
    if 'user_id' in session and session['user_id'] == target_user_id:
        return redirect(url_for('profile'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    info_sql = """
    SELECT u.name, u.organization, a.username,
           COALESCE(AVG(c.rating), 0) as avg_score,
           COUNT(c.comment_id) as review_count
    FROM ((users u LEFT JOIN account a 
            ON u.user_id = a.user_id) LEFT JOIN post p 
            ON u.user_id = p.user_id) LEFT JOIN comment c 
            ON p.post_id = c.post_id
    WHERE u.user_id = %s
    GROUP BY u.user_id, a.username;
    """
    cur.execute(info_sql, (target_user_id,))
    user_info = cur.fetchone()

    if not user_info:
        flash('找不到該使用者！')
        return redirect(url_for('index'))

    post_sql = """
    SELECT p.post_id,  p.description, p.post_time, p.available,
           (SELECT COUNT(*) FROM item i WHERE i.post_id = p.post_id) as item_count
    FROM post p
    WHERE p.user_id = %s
    ORDER BY p.post_time DESC
    """
    cur.execute(post_sql, (target_user_id,))
    public_posts = cur.fetchall()

    comments_sql = """
    SELECT c.comment_str, c.rating, c.comment_time, p.description
    FROM (comment c LEFT JOIN post p
            ON c.post_id = p.post_id)
    WHERE p.user_id = %s
    ORDER BY c.comment_time DESC
    """
    cur.execute(comments_sql, (target_user_id,))
    past_comments = cur.fetchall()

    phone_sql = """
    SELECT phone_number
    FROM phone
    WHERE user_id = %s
    """
    cur.execute(phone_sql, (target_user_id,))
    phone = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('public_profile.html', user=user_info, posts=public_posts, comments=past_comments, phones=phone)

@app.route('/add_phone', methods=['GET', 'POST'])
def add_phone():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        phone = request.form.get('phone')
        
        if not phone:
            flash('電話號碼不能為空！')
        else:
            try:
                check_phone = """
                SELECT user_id 
                FROM phone 
                WHERE phone_number = %s
                """
                cur.execute(check_phone, (phone,))
                existing = cur.fetchone()
                
                if existing:
                    if existing[0] == session['user_id']:
                        flash('你已經綁定過這支電話囉！')
                    else:
                        flash('這支電話已經被其他帳號使用了！')
                else:
                    insert_phone = """
                    INSERT INTO phone (phone_number, user_id)
                    VALUES (%s, %s)
                    """
                    cur.execute(insert_phone, (phone, session['user_id']))
                    conn.commit()
                    flash('電話新增成功！')
                    return redirect(url_for('profile'))
                    
            except Exception as e:
                conn.rollback()
                flash(f'新增失敗: {e}')
    
    cur.close()
    conn.close()
    
    return render_template('add_phone.html')

from datetime import datetime, timedelta # 記得在檔案最上面 import

@app.route('/post_item', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if request.method == 'POST':
        description = request.form.get('description')
        location_name = request.form.get('location_name')
        city = request.form.get('city', '新竹市')
        district = request.form.get('district', '東區')
        street = request.form.get('street', '大學路')
        number = request.form.get('number', '1001號')
        
        expiration_date = request.form.get('expiration_date')
        if not expiration_date:
             expiration_date = datetime.now() + timedelta(days=7)

        item_names = request.form.getlist('item_name') 
        quantities = request.form.getlist('quantity')
        category_ids = request.form.getlist('category_id')

        if not description or not item_names:
            flash('請填寫完整資訊！')
            return redirect(url_for('post_item'))

        try:
            cur.execute("""
                INSERT INTO post (user_id, description)
                VALUES (%s, %s) RETURNING post_id
            """, (session['user_id'], description))
            new_post_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO location (location_name, city, district, street, number)
                VALUES (%s, %s, %s, %s, %s) RETURNING location_id
            """, (location_name, city, district, street, number))
            new_location_id = cur.fetchone()[0]

            for i_name, i_qty, i_cat in zip(item_names, quantities, category_ids):
                if not i_name.strip(): 
                    continue

                cur.execute("""
                    INSERT INTO item 
                    (category_id, post_id, location_id, item_name, expiration_date, quantity)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (i_cat, new_post_id, new_location_id, i_name, expiration_date, i_qty))

            conn.commit()
            flash(f'成功刊登貼文！包含了 {len(item_names)} 樣物品。')
            return redirect(url_for('index'))

        except Exception as e:
            conn.rollback()
            flash(f'刊登失敗: {e}')
            return redirect(url_for('post_item'))
        finally:
            cur.close()
            conn.close()

    cur.execute("SELECT * FROM categories ORDER BY category_id ASC")
    categories = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('post_item.html', categories=categories)

# 啟動伺服器
if __name__ == '__main__':
    app.run(debug=True)