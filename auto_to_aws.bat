for /l %%x in () do (
    echo "scp to AWS trtrader EC2"
    python html_converter.py
    scp -i defaultkeypair.pem data/index.html ubuntu@13.209.99.197:~/trtrader/
    scp -i defaultkeypair.pem data/trtrader_status.html ubuntu@13.209.99.197:~/trtrader/
    scp -i defaultkeypair.pem data/trade_log.html ubuntu@13.209.99.197:~/trtrader/
    scp -i defaultkeypair.pem man_trtrader.html ubuntu@13.209.99.197:~/trtrader/
    TIMEOUT 30
)