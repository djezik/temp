#DB_LINK = "sqlite:///test_db"
from os import environ

#DB_LINK = environ["DATABASE_URL"]
DB_LINK = "postgresql://localhost/botdb"

# REQUEST_KWARGS = {
#     'proxy_url': 'socks5://vpn.qjex.xyz:1080',
#     'urllib3_proxy_kwargs': {
#         'username': 'qjex',
#         'password': 'proxy',
#     }
# }
#
# TOKEN = r"654559011:AAHE57UO_WLgp-GufU7bqiBrXUYSm_-GiWo"

REQUEST_KWARGS = None

TOKEN = r"738736161:AAHjw1uqGlLvhWw83LcVW_uZL_V4DFS6ICM"
#r"680828837:AAFF4XE3c49N3j8_jdtkwv0yVDW9BSujqlo
BOT_LINK = "djezikcrypto_bot"

# # # # # Time and money constants # # # # #

# Задержка просмотра постов (В минутах)
VIEW_GIFT_DELAY = 1440

# Минимальная сумма для вывода
MINIMAL_WITHDRAWAL_AMOUNT = 100

# Размер награды за приглашение друга
REFERRAL_BONUS = 3

# Награда за подписку на канал
SUBSCRIPTION_BONUS = 2

TIME_EPSILON = 0
