HelloAction.GreetingInput input = new HelloAction.GreetingInput();
input.userName = 'Sam';
List<HelloAction.GreetingInput> inputs = new List<HelloAction.GreetingInput>{input};
List<HelloAction.GreetingOutput> outputs = HelloAction.getGreeting(inputs);
System.debug('RESULT: ' + outputs[0].greetingMessage);
