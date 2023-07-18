import concurrent
import time
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import pymongo
import requests
from dotenv import load_dotenv
from streamlit import empty, text_input, button, columns, selectbox, altair_chart, title, tabs, spinner, \
    success, set_page_config

load_dotenv()


class Chart:
    def __init__(self):
        self.chart_container = empty()

    @staticmethod
    def fetch_chart_data(items):
        """Fetch and prepare data for the chart."""
        chart_data = pd.DataFrame({
            'Time to interactive (s)': [
                data['audits']['interactive']['numericValue'] / 1000
                for item in items for data in item['data']
            ],
            'URL': [
                data['requestedUrl']
                for item in items for data in item['data']
            ],
            'Timestamp': [
                item['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                for item in items for data in item['data']
            ]
        })
        return chart_data

    @staticmethod
    def draw_chart(chart_data):
        """Draw a line chart with the fetched chart data."""
        chart = alt.Chart(chart_data, title='Loading time').mark_bar(
            opacity=1,
            size=10
        ).encode(
            x=alt.X('Timestamp', title='Timestamp', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Time to interactive (s):Q', stack=False),
            column=alt.Column('URL:N', title='URL'),
            color=alt.Color('URL:N')
        ).properties(width=300).configure_view(stroke='transparent')

        altair_chart(chart, use_container_width=False)


class DbHandler:
    def __init__(self):
        self.client = self.init_connection()

    @staticmethod
    def init_connection():
        """Connect to MongoDB and return client."""
        return pymongo.MongoClient()

    def fetch_data(self, current_urls):
        """Fetch data from MongoDB."""
        db = self.client.timeit
        items = list(db.measurements.find({'urls': current_urls}))
        return items

    def fetch_urls(self):
        """Fetch distinct URLs from MongoDB."""
        db = self.client.timeit
        items = list(db.measurements.distinct('urls'))
        return items

    def insert_data(self, data1, data2):
        """Insert data to MongoDB."""
        db = self.client.timeit
        result = db.measurements.insert_one({
            'data': [data1, data2],
            'timestamp': datetime.now(timezone.utc),
            'urls': ' | '.join([data1['requestedUrl'], data2['requestedUrl']])
        })
        return result.inserted_id


def fetch_response_data(url):
    return requests.post(
        "http://localhost:3000/stats",
        headers={'Cache-Control': 'no-cache', 'Content-Type': 'application/json'},
        json={
            "url": url,
            "config": {
                "extends": "lighthouse:default",
                "settings": {"onlyAudits": ["first-contentful-paint", "interactive"]}
            }
        }
    ).json()


def main():
    set_page_config('⏱️ TimeIt')
    title('⏱️ TimeIt')
    db_handler = DbHandler()
    chart = Chart()
    tab1, tab2 = tabs(['Run Test', 'Results'])

    with tab1:
        col1, col2 = columns(2)

        with col1:
            url1 = text_input('URL 1', 'http://192.168.1.157:8070')

        with col2:
            url2 = text_input('URL 2', 'http://192.168.1.157:8075')

        if button('Run test'):
            with spinner('Taking Measurements...'):
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future1 = executor.submit(fetch_response_data, url1)
                    future2 = executor.submit(fetch_response_data, url2)
                    response_data1 = future1.result()
                    response_data2 = future2.result()

                time.sleep(5)
            success_message = success('Done!')

            db_handler.insert_data(response_data1, response_data2)

            time.sleep(5)

            success_message.empty()

    with tab2:
        current_urls = selectbox('URL', db_handler.fetch_urls())
        items = db_handler.fetch_data(current_urls)
        chart_data = chart.fetch_chart_data(items)
        chart.draw_chart(chart_data)


if __name__ == "__main__":
    main()
