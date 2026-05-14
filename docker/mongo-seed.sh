#!/bin/bash
set -e

MONGO_HOST="${MONGO_HOST:-mongo1}"

echo "Waiting for replica set primary..."
until mongosh --host "$MONGO_HOST" --eval "rs.isMaster().ismaster" 2>/dev/null | grep -q true; do
  sleep 2
done

echo "Seeding restaurant and menu data..."
mongosh --host "$MONGO_HOST" restaurant --eval "
  // Restaurants — keyed on name for idempotency
  const restaurants = [
    {
      name: 'Burger Palace',
      address: '10 Khreshchatyk St, Kyiv',
      cuisine: 'American',
      rating: 4.5,
      is_active: true,
    },
    {
      name: 'Sushi Garden',
      address: '22 Lesi Ukrainky Blvd, Kyiv',
      cuisine: 'Japanese',
      rating: 4.8,
      is_active: true,
    },
  ];

  for (const r of restaurants) {
    db.restaurants.updateOne(
      { name: r.name },
      { \$setOnInsert: r },
      { upsert: true }
    );
  }
  print('Restaurants seeded.');

  const burgerPalace = db.restaurants.findOne({ name: 'Burger Palace' });
  const sushiGarden  = db.restaurants.findOne({ name: 'Sushi Garden' });

  // Menu items — keyed on (restaurant_id, name) for idempotency
  const menuItems = [
    // Burger Palace
    { restaurant_id: burgerPalace._id.toString(), name: 'Classic Cheeseburger', description: 'Beef patty with cheddar, lettuce, tomato', price: 8.99,  is_available: true },
    { restaurant_id: burgerPalace._id.toString(), name: 'Bacon Double Burger',  description: 'Double beef patty with crispy bacon',      price: 11.99, is_available: true },
    { restaurant_id: burgerPalace._id.toString(), name: 'Veggie Burger',        description: 'Plant-based patty with avocado spread',    price: 9.49,  is_available: true },
    { restaurant_id: burgerPalace._id.toString(), name: 'Loaded Fries',         description: 'Fries topped with cheese sauce and jalapeños', price: 4.99, is_available: true },

    // Sushi Garden
    { restaurant_id: sushiGarden._id.toString(),  name: 'Salmon Nigiri (2 pcs)',  description: 'Fresh Atlantic salmon over pressed rice',   price: 6.99,  is_available: true },
    { restaurant_id: sushiGarden._id.toString(),  name: 'Tuna Roll (8 pcs)',      description: 'Bluefin tuna, cucumber, sesame',            price: 12.99, is_available: true },
    { restaurant_id: sushiGarden._id.toString(),  name: 'Dragon Roll (8 pcs)',    description: 'Shrimp tempura topped with avocado',        price: 15.49, is_available: true },
    { restaurant_id: sushiGarden._id.toString(),  name: 'Miso Soup',             description: 'Traditional dashi broth with tofu and wakame', price: 2.99, is_available: true },
  ];

  for (const item of menuItems) {
    db.menu_items.updateOne(
      { restaurant_id: item.restaurant_id, name: item.name },
      { \$setOnInsert: item },
      { upsert: true }
    );
  }
  print('Menu items seeded.');
"

echo "Seed complete."
