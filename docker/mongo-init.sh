#!/bin/bash
set -e

MONGO_HOST="${MONGO_HOST:-mongo1}"

echo "Waiting for $MONGO_HOST to be ready..."
until mongosh --host "$MONGO_HOST" --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  sleep 2
done

echo "Initializing replica set..."
mongosh --host "$MONGO_HOST" --eval "
  try {
    rs.status();
    print('Replica set already initialized.');
  } catch (e) {
    rs.initiate({
      _id: 'rs0',
      members: [
        { _id: 0, host: 'mongo1:27017' },
        { _id: 1, host: 'mongo2:27017' },
        { _id: 2, host: 'mongo3:27017' }
      ]
    });
    print('Replica set initialized.');
  }
"

echo "Waiting for primary election..."
until mongosh --host "$MONGO_HOST" --eval "rs.isMaster().ismaster" 2>/dev/null | grep -q true; do
  sleep 2
done

echo "Replica set is ready. Status:"
mongosh --host "$MONGO_HOST" --eval "rs.status().members.forEach(m => print(m.name, m.stateStr))"
