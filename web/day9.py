from flask import Flask, render_template, request, session, redirect
import requests
from bs4 import BeautifulSoup
import re
from datetime import date, timedelta, datetime
import os
from selenium import webdriver
import pymysql
from konlpy.tag import Kkma
import base64

app = Flask(__name__, template_folder ='templates', static_folder='static')
app.dev = 'development'
app.debug = True
app.secret_key = 'klsadjfklsdalfshdkfhlkdsfjlkasfsdafhdfssdfh'
kkma = Kkma()

db = pymysql.connect(
    user='root',
    passwd='abcd123',
    host='localhost',
    db='membership',
    charset='utf8',
    cursorclass=pymysql.cursors.DictCursor
)

def get_menu():
    cursor = db.cursor()
    cursor.execute("SELECT id, title FROM topic order by title desc")
    return cursor.fetchall()

@app.route('/')
def index():
# def generate_menu():
    cursor = db.cursor()
    cursor.execute("SELECT id, title FROM topic order by title desc")
    # menu = [f"<li><a href='{e['id']}'>{e['title']}</a></li>" for e in cursor.fetchall()]
    # return '\n'.join(menu)
    return render_template('index.html',
                            menu=cursor.fetchall(),
                            user=session.get('user'))

# session을 활용하여 로그인 기능을 구현한다. 
# index 페이지 
# 로그인이 안되어있을 때에는 로그인, 회원가입 링크를 보여주고,
# 로그인이 되어있을 때에는 로그아웃, 회원탈퇴 링크를 보여준다.
# 회원로그인 /login, 회원로그아웃 /logout 
# 회원가입 /join, 회원탈퇴 /withdrawal

@app.route('/login', methods=['get','post'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    cursor = db.cursor()
    cursor.execute(f"""
        select id, profile, pw from membership_list
        where id = '{ request.form['userid'] }' and
                pw = SHA2('{  request.form['password'] }', 256)
        """)   
    user = cursor.fetchone()
    if user:
        session['user'] = user
    # session['user'] = {'name': 'sookbun', 'profile':'engineer'}
        return redirect('/')
    else:
        return render_template('login.html', msg="로그인 정보를 확인하세요.")

@app.route('/logout', methods=['get','post'])
def logout():
    session.pop('user')
    return redirect('/')

@app.route('/join', methods=['get','post'])
def join():
    if request.method == 'GET':
        return render_template('join.html')

    cursor = db.cursor()
    cursor.execute(f"insert into membership_list values('{request.form['userid']}', '{request.form['profile']}', sha2('{request.form['password']}',256))")   
    db.commit()

    return redirect('/login')


@app.route('/withdrawal')
def withdrawal():

    cursor = db.cursor()
    user = session.pop('user',None)
    cursor.execute(f"delete from membership_list where id = '{user['id']}'") 
    db.commit()

    return redirect('/')

# /news/ranking 
# 다음 랭킝 뉴스 크롤링 - https://media.daum.net/ranking/
# 날짜를 입력받는 폼을 보여주고, 날짜를 입력하고 버튼을 클릭하면 해당 날짜의 뉴스 랭킹 리스트를 보여준다. 
# 뉴스의 리스트 url은 다음과 같이 한다. "/news/words?url=<해당뉴스의 url>"

@app.route('/news/ranking', methods=['get','post'])
def news_ranking():
    if request.method == "GET":
        return render_template("news_ranking.html")
    
    url = "https://media.daum.net/ranking/?regDate="
    date = request.form.get('date')
    # date = date.strftime('%Y%m%d')
    rq_url = url+date
    res = requests.get(rq_url)
    links = [(tag.strong.a.get_text(),tag.strong.a.get('href')) for tag in BeautifulSoup(res.content, 'html.parser').select('#mArticle div.cont_thumb')]

    return render_template('news_ranking.html',links=links)

# /news/words?url=<해당뉴스의 url>
# 다음 뉴스 크롤링 - 컨텐츠 단어 랭킹 추출
# 뉴스의 컨텐츠를 읽어서 단어 카운트를 하고, 정렬하여 보여준다.

@app.route('/news/words')
def news_word():
    url = request.args.get('url')
    
    res = requests.get(url)
    texts = [tag.get_text() for tag in BeautifulSoup(res.content, 'html.parser').select('#harmonyContainer')]
    texts = ' '.join(texts)
    texts = kkma.pos(texts)
    texts = [w for w in texts if w[1] in ['NNG', 'NNP']]
    texts =[(w, texts.count(w)) for w in set(texts)]
    texts = sorted(texts, key=lambda x: x[1], reverse=True)

    return render_template('news_ranking.html',texts=texts)


# /downloads/<검색어>
# 다음 구글 이미지 크롤링
# 키워드로 검색된 구글 이미지를 디렉토리에 다운로드한다.
# url로 불러오는 경우와 바이너리가 직접 들어있는 경우 모두 다운로드한다.

@app.route('/download/<keyword>')
def download(keyword):

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver=webdriver.Chrome('chromedriver',options=options)
    driver.implicitly_wait(3)

    url = f"https://www.google.com/search?q={keyword}&tbm=isch"

    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    img_links = []
    for i in soup.select('img.rg_i'):
        try:
            img_links.append(i.attrs['src'])
        except KeyError:
            img_links.append(i.attrs['data-src'])

    # create directory
    os.makedirs(f'static/download/{keyword}', exist_ok=True)

    # Download
    for i, link in enumerate(img_links):
        if link[:4] == "data" :
            link=base64.b64decode(link.split(',')[1])
            with open(f'static/download/{keyword}/{i}.jpg', 'wb') as f:
                f.write(link)
        else:
            res = requests.get(link)
            with open(f'static/download/{keyword}/{i}.jpg', 'wb') as f:
                f.write(res.content)

    return render_template('download.html',img_links=img_links)

# (옵션)
# 다음 랭킹 뉴스 페이지(https://media.daum.net/ranking/)의
# 하위 탭 메뉴와 페이지들을 확인하고, 크롤링을 통해 
# 유용한 기능을 파트너와 함께 자유롭게 기획하여 추가해 봅시다.

@app.route('/news/ranking/age', methods=['get','post'])
def news_ranking_age():
    if request.method == "GET":
        return render_template("news_ranking_age.html")
    
    url = "https://media.daum.net/ranking/age/?regDate="
    date = request.form.get('date')
    # date = date.strftime('%Y%m%d')
    rq_url = url+date
    res = requests.get(rq_url)
    links = [(tag.a.get_text(),tag.a.get('href')) for tag in BeautifulSoup(res.content, 'html.parser').select('.item_20s .rank_female .list_age li')]

    return render_template('news_ranking_age.html',links=links)

app.run()