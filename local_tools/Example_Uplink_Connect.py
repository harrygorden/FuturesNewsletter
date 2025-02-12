import anvil.server
import code

anvil.server.connect("Anvil_Server_Uplink_ID")
print("Connected to Anvil server.")
print("Example: Run `result = anvil.server.call('get_data', 'Alice')` and then `print(result)` to test the server function.")

@anvil.server.callable
def get_data(name):
  print(f"Hello from your own machine, {name}!")
  return [1, 2, 4, 8]

print("Entering interactive console session. Type exit() to quit.")
code.interact(local=globals())