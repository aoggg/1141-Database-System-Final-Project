# Database final project

## 前置處理

內容在 [final project](./final%20project/) 裏。

### 1. 先安裝一些套件
放在 [requirements](./final%20project/requirements.txt) 裡面，先確保路徑是對的，然後執行
```bash
pip install -r requirements.txt
```
應該就好了

### 2. 建立資料庫

先建一個自己的資料庫，然後執行 [database](./final%20project/database/) 裡面的檔案，有兩個。[schema.sql](./final%20project/database/schema.sql) 是在建 table 的，還有一個 trigger 也在裡面。
[data.sql](./final%20project/database/data.sql) 是 AI 依據前面的 schema 生的假資料，應該有符合規定。

schema 的部分主要根據 milestone2 裡的 ERdiagram 畫出來，但有一些細微的更動，之後應該會再重畫一次。
1. 把 phone number 獨立出來成一個單獨的表
2. 多了 account，是在記各個 user 的 username, 以及密碼。為了方便，前 100 個 users 分別是 user1~user100，然後密碼都是 1234，資料庫裡的密碼是記 hash 過後的字串，所以不會直接看到 1234（明文）。

有在思考是不是應該要放個頭貼或是貼文是不是要有照片之類的，但目前應該不是主要功能。

### 3. 建立 .env 檔案

創一個 `.env` 檔案，裡面放兩行。
```
DB_PASSWORD=postgres的密碼
SECRET_KEY=應該是隨便一個字串就好了
```
### 4. 啟動

```bash
python app.py
```
就可以ㄌ


## 目前的狀態
- [x] 會員登入/登出 (Session)
- [x] 索取功能 (用 Trigger 扣庫存)
- [ ] 刊登物品 (TODO)
- [ ] 個人頁面 (TODO)
- [ ] 可以切換以貼文為主或是以物品為主兩個瀏覽方式（TODO）
- [ ] 索取完可以針對剛剛索取的內容評論一次（TODO）
- [ ] 頭貼、以及貼文附照片？