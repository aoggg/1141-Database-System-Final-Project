from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") # 這邊可以隨便放一個字串，寫在 .env 裡面

# 這裡設定資料庫
DB_HOST = "localhost"
DB_NAME = "final"  # 資料庫的名稱
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
    view_mode = request.args.get('view', 'post')
    
    # 連上資料庫
    conn = get_db_connection()
    
    # 建立 Cursor (游標)
    # cursor_factory=psycopg2.extras.DictCursor 是一個小技巧
    # 讓我們等一下可以用 item['item_name'] 這種直觀的方式取值
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if view_mode == 'item':
        cnt_sql = """
        SELECT sum(quantity)
        FROM item
        WHERE quantity > 0
        """
        cur.execute(cnt_sql)
        result = cur.fetchone()
        cnt = result[0] if result and result[0] else 0

        sql = """
        SELECT i.item_id, i.item_name, i.quantity, i.expiration_date,
               c.name,
               p.description, p.available, l.location_name, l.city, l.district, l.street, l.number
        FROM ((item i LEFT JOIN post p
                ON i.post_id = p.post_id) LEFT JOIN location l
                ON i.location_id = l.location_id) LEFT JOIN categories c
                ON i.category_id = c.category_id
        WHERE i.quantity > 0
        ORDER BY i.quantity DESC,
                 p.post_id DESC,
                 c.category_id ASC
        """
        cur.execute(sql)
        items = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('index_item.html', view_mode='item', items=items, total=cnt)
    
    else:
        sql = """
        SELECT i.item_id, i.item_name, i.quantity, i.expiration_date,
               c.name,
               p.description, p.available, p.post_id,
               l.location_name, l.city, l.district, l.street, l.number
        FROM ((item i LEFT JOIN post p
                ON i.post_id = p.post_id) LEFT JOIN location l
                ON i.location_id = l.location_id) LEFT JOIN categories c
                ON i.category_id = c.category_id
        WHERE p.available = TRUE
        ORDER BY p.post_id DESC,
                 c.category_id ASC
        """
        cur.execute(sql)
        data = cur.fetchall()

        posts_map = {}

        for i in data:
            p_id = i['post_id']
            if p_id not in posts_map:
                posts_map[p_id] = {
                    'post_id': p_id,
                    'description': i['description'],
                    'available': i['available'],
                    'items': []
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

        return render_template('index_post.html', view_mode="post", posts=list(posts_map.values()))

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

    return render_template('profile.html', user=user_info, claims=my_claims, posts=my_posts)

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

# 啟動伺服器
if __name__ == '__main__':
    app.run(debug=True)