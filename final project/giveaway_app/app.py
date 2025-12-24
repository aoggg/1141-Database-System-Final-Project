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
    # 連上資料庫
    conn = get_db_connection()
    
    # 建立 Cursor (游標)
    # cursor_factory=psycopg2.extras.DictCursor 是一個小技巧
    # 讓我們等一下可以用 item['item_name'] 這種直觀的方式取值
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    sql = """
    SELECT i.item_name, i.quantity, p.description, p.available, l.location_name, i.item_id
    FROM (item i
            JOIN post p ON i.post_id = p.post_id)
            JOIN location l ON l.location_id = i.location_ID
    ORDER BY 
        i.quantity DESC,
        p.post_id DESC   
    LIMIT 100;
    """
    
    cur.execute(sql)
    
    # 抓取所有結果
    items = cur.fetchall()
    
    # 關閉連線
    cur.close()
    conn.close()
    return render_template('index.html', items=items)

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

# 啟動伺服器
if __name__ == '__main__':
    app.run(debug=True)