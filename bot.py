import time
import pyupbit
from datetime import datetime
from pytz import timezone
import requests

SELECTED_COINS = ['XRP', 'ETC', 'VET', 'SC', 'GAS', 'BTT', 'BCH', 'BTC', 'EOS', 'TRX',
                    'NEO', 'QTUM', 'BTG', 'ETH', 'BCHA', 'THETA', 'XEM', 'LTC', 'ADA']

GROWING_PERIOD = 5
BETTING_BUDGET = 30000
MAX_NUM_COIN = 5
SPREAD_GAP = 0.002


with open("key.txt") as f:
    lines = f.readlines()
    key = lines[0].strip()
    secret = lines[1].strip()
    mytoken = lines[2].strip()  # slack bot token

upbit = pyupbit.Upbit(key, secret)

def post_message_to_slack(channel, text):
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+mytoken},
        data={"channel": channel,"text": text}
    )
    print(response)

def candidate_coins():
    if SELECTED_COINS:
        return map(lambda x: 'KRW-{0}'.format(x), SELECTED_COINS)
    candidate_coin = map(lambda x: x['market'], upbit.get_markets())
    return filter(lambda x: x.startswith('KRW'), candidate_coin)


def is_growing_market(market):
    prices = pyupbit.get_ohlcv(market, "day", count=GROWING_PERIOD)
    return prices[0]['trade_price'] > prices[-1]['trade_price']


def get_market_noise(market, prices):
    
    print(market)
    print(prices)
    
    prices['noise'] = 1 - abs(prices['close'] - prices['open']) / (prices['high'] - prices['low'])
    print(prices['noise'])
    print(prices['noise'].mean())
    return prices['noise'].mean()


def get_betting_ratio(market, prices):
    '''
    3일~20일의 18개의 이동 평균선을 계산
    이동평균선 스코어 = 각 이동평균선을 넘은 개수/18
    e.g., 3일의 이동 평균선 = (1일전 종가 + 2일전 종가 + 3일전 종가)/3
          => 만약 현재 가격이 3일의 이동 평균 가격 보다 높으면 score 1/18 더한다
    '''
    
    print('\n[{0}]\n {1}'.format(get_betting_ratio.__name__, prices))
    score = 0
    if len(prices) < 21:
        print('prices len: {0}'.format(len(prices)))
        return 0

    sum_prices = sum(prices['close'][:18])
    open_prices = prices['open'][20]

    for w in range(17, 1, -1):
        moving_average = prices['close'][w:20].mean()
        if moving_average < open_prices:
            score += 1/18.0

    print(score)
    return score

def buy(market, budget):
    print('buy market:{0}, budget:{1}'.format(market, budget))
    result = upbit.buy_market_order(market, budget)
    print(result)


def sell(market, amount):
    print('sell market:{0}, amount:{1}'.format(market, amount))
    result = upbit.sell_market_order(market, amount)
    print(result)

def retry_get_ohlcv(market, day, count):
    prices = pyupbit.get_ohlcv(market, day, count)
    while prices is None:
        print('retry_get_ohlcv.. market({0}), day({1}), count({2})'.format(market, day, count))
        prices = pyupbit.get_ohlcv(market, day, count)
        time.sleep(1)
    return prices

if __name__ == '__main__':
    print('main')
    #trade_markets = list(candidate_coins())
    trade_markets = pyupbit.get_tickers("KRW")
    print(trade_markets)
    print('market count: {0}'.format(len(trade_markets)))
    already_buy = {}
    coin_noise = {}
    coin_betting_ratio = {}
    coin_investable = MAX_NUM_COIN

    for market in trade_markets:
        prices = retry_get_ohlcv(market, "day", count=21)

        coin_noise[market] = get_market_noise(market, prices)
        coin_betting_ratio[market] = get_betting_ratio(market, prices)
        time.sleep(0.33)

    trade_markets = list(filter(lambda m: coin_betting_ratio[m] > 0, trade_markets))

    while True:
        
        t = datetime.now(timezone('Asia/Seoul'))
        if t.minute == 0:
            print('{0} ... alive'.format(t))

        for market in trade_markets:
            if market in already_buy:
                if t.hour == 8 and t.minute >= 59:
                    account = upbit.get_balance(market)
                    #sell(market, account)
                    coin_investable += 1
                continue

            if coin_investable <= 0:
                break

            candles = retry_get_ohlcv(market, "day", count=2)
            _range = candles['high'][0] - candles['low'][0]

            today_opening = candles['open'][1]
            today_current = candles['close'][1]

            k = _range * coin_noise[market] * 0.5

            over_ratio = today_current / (today_opening + k)

            if over_ratio > 1.0:
                print('market:{0}, coin_betting_ratio:{1}, over_ratio:{2}'.format(market, coin_betting_ratio[market], over_ratio))
                post_message_to_slack("#personal",
                                        "market:{0}, coin_betting_ratio:{1}, over_ratio:{2}".format(market, coin_betting_ratio[market], over_ratio))
                #buy(market, BETTING_BUDGET * coin_betting_ratio[market])
                already_buy[market] = True
                coin_investable -= 1

        time.sleep(1)
