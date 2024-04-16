import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv
import os
import streamlit as st
import pandas as pd
from contextlib import closing

load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

def get_db_connection():
    conn = psycopg2.connect(dbname=DB_NAME, 
                            user=DB_USER, 
                            host=DB_HOST, 
                            password=DB_PASS, 
                            sslmode='require')
    return conn

# Initialize database
def init_db():
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255),
                    price NUMERIC,
                    rating VARCHAR(20),
                    description TEXT
                );
                """
            )
            conn.commit()


def scrape_books():
    base_url = 'http://books.toscrape.com/catalogue/'
    current_page = 'page-1.html'
    books = []

    while current_page:
        url = f'{base_url}{current_page}'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Scraping books on the current page
        for article in soup.find_all('article', class_='product_pod'):
            title = article.h3.a['title']
            book_url = base_url + article.h3.a['href'].replace('../../../', '')
            price = article.find('p', class_='price_color').text.replace('Â', '')
            rating = article.p['class'][1]  # Assumes the rating is in the second class attribute

            # Fetching book description
            book_response = requests.get(book_url)
            book_soup = BeautifulSoup(book_response.text, 'html.parser')
            description_tag = book_soup.find('meta', attrs={'name': 'description'})
            description = description_tag['content'].strip() if description_tag else 'No description available'
            
            books.append({
                'title': title,
                'price': price,
                'rating': rating,
                'description': description
            })

        # Check if there's a next page
        next_button = soup.find('li', class_='next')
        if next_button:
            current_page = next_button.a['href']
        else:
            break  # No more pages

        print(f'Scraped {len(books)} books so far')
    return books

thebook = scrape_books()

def store_books(books):
    connection = psycopg2.connect(dbname=DB_NAME, 
                        user=DB_USER, 
                        host=DB_HOST, 
                        password=DB_PASS, 
                        sslmode='require')
    cursor = connection.cursor()
    
    for book in books:
        cursor.execute(
            "INSERT INTO books (title, price, rating, description) VALUES (%s, %s, %s, %s)",
            (book['title'], book['price'], book['rating'], book['description'])
        )
    connection.commit()
    cursor.close()
    connection.close()

def query_books(connection, search_query, order_by, rating_filter):
    filter_query = ''
    if rating_filter != 'Any':
        filter_query = f"AND rating = '{rating_filter}'"

    with closing(connection.cursor()) as cur:
        cur.execute(f"""
            SELECT * FROM books
            WHERE title LIKE %s OR description LIKE %s
            {filter_query}
            ORDER BY {order_by}
        """, ('%' + search_query + '%', '%' + search_query + '%'))
        result = cur.fetchall()
        return pd.DataFrame(result, columns=['id', 'title', 'price', 'rating', 'description'])

def main():
    st.title('Book Explorer')
    init_db()

    search = st.text_input('Search books by title or description')
    rating_filter = st.selectbox('Filter by rating', options=['Any', 'One', 'Two', 'Three', 'Four', 'Five'])
    order_by = st.selectbox('Order by', options=['price', 'rating'])

    if st.button('Search'):
        with closing(get_db_connection()) as conn:
            books_df = query_books(conn, search, order_by, rating_filter)
            if books_df.empty:
                st.write("No books found.")
            else:
                st.write(books_df)

if __name__ == '__main__':
    main()