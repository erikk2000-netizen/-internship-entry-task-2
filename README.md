# -internship-entry-task-2
Игрушечный сервис, имитирующий прохождение платежей. Использует Python (sqlalchemy, asyncio, multiprocessing) и MySQL DB.

Команда для запуска: docker compose up --build
Тестировался на виртуальной машине Linux, созданной из стандартного образа https://releases.ubuntu.com/noble/ubuntu-24.04.4-live-server-amd64.iso, с параметрами по умолчанию, с 8ГБ RAM и 50GB HDD.

База данных MySQL создается автоматически при первой сборке контейнера. Но может не создаться, например, если том для хранилища МуSQL уже не пустой. В таком случае необходимо в МуSQL выполнить запросы из файла init.sql. Это можно сделать, используя PhpMyAdmin по ссылке http://<Virtual Machine IP>:8088 (root/rootpassword)

Тестировался из браузера FireFox (Dev Tools, Network Tab, Edit and Resend request form)
План тестирования.

1. Сделать запрос [GET http://<Virtual Machine IP>:8080/health]. Убедиться, что ответ приходит с HTTP статус-кодом 200.
2. Сделать запрос [POST http://<Virtual Machine IP>:8080/operations] с некорректными данными (неправильная валюта, неправильная сумма, отсутствие идентификатора). Убедиться что получаем ответ с описанием ошибки.
3. Сделать запрос [POST http://<Virtual Machine IP>:8080/operations] с корректными данными и с operationId = "op". Убедиться, что ответ приходит с HTTP статус-кодом 200 и с данными новосозданной операции в статусе "CREATED".
4. Сделать запрос [POST http://<Virtual Machine IP>:8080/operations] с формально корректными данными, но с таким же operationId = "op", как в предыдущем запросе. Убедиться, что ответ приходит с HTTP статус-кодом 409.
5. Сделать запрос [POST http://<Virtual Machine IP>:8080/operations/op/submit]. Убедиться, что ответ приходит с HTTP статус-кодом 202.
6. Сделать через пару минут повторно запрос [POST http://<Virtual Machine IP>:8080/operations/op/submit]. Убедиться, что ответ приходит с HTTP статус-кодом 202. И с данными операции, как правило, в статусе CОМPLETED.
7. Когда для какого-то operationId получился статус CОМPLETED или REJECTED - убедитесь, что во всех четырех таблицах MySQL (можно использовать PhpMyAdmin по ссылке http://<Virtual Machine IP>:8088) - tvents, operations, receipts и submits хранятся корректные записи.
8. Сделать запрос [GET http://<Virtual Machine IP>:8080/operations/op]. Убедиться, что ответ приходит с HTTP статус-кодом 200 и с корректными данными операции "op".
9. Сделать запрос [GET http://<Virtual Machine IP>:8080/operations/op/events]. Убедиться, что ответ приходит с HTTP статус-кодом 200 и с корректными данными событий смены статуса операции "op".


