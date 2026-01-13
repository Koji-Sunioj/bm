# What is this

Started a while ago, to learn NGINX and FastAPI in a very basic web application and thought it would be cool to make it look like older heavy metal retail websites of the early 2000's. As such, it felt suitable to folder more old school and bare bones development patterns.

## Features

1. Customers can login (I have a "guest list" to prevent bots) and add to cart, order and search through music albums. They can also preview music samples from the album.
2. All changes to the backend server and front end files are mirrored on the remote EC2 server with github actions.
3. I am using [Atlas](https://atlasgo.io/) to update the database as well, if the schema file is different than what already exists.
4. There is an admin section, which the admin can send purchase orders to lambda server. When order is confirmed and shipped, admin can mark trigger restock of items. I use HMAC for server-to-server authentication.
5. EC2 initiation and update done in a seperate Cloudformation template, using [Cloud Config](https://cloudinit.readthedocs.io/en/latest/index.html) as bare metal server.
6. Since this is an "old school" app, I use stored functions (or procedures) to process databasse transactions
