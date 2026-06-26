if __name__ == '__main__':
    from twilio.rest import Client

    account_sid = 'ACb6e9976360e7aa7d3ec77cd965e63815'
    auth_token = '88b50998780b4989038c334f3fb0d1dc'
    client = Client(account_sid, auth_token)

    message = client.messages.create(
      from_='whatsapp:+14155238886',
        body='Hello Mohammed Sulthan, Your SmartSpend expense was added successfully.',
      to='whatsapp:+917845782348'
    )

    print(message.sid)