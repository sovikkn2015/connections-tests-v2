// Test the HelloAction Apex class directly
HelloAction.GreetingInput input = new HelloAction.GreetingInput();
input.userName = 'Sam';

List<HelloAction.GreetingInput> inputs = new List<HelloAction.GreetingInput>{ input };
List<HelloAction.GreetingOutput> outputs = HelloAction.getGreeting(inputs);

System.debug('=== GREETING RESULT ===');
System.debug(outputs[0].greetingMessage);

// Test without a name
HelloAction.GreetingInput input2 = new HelloAction.GreetingInput();
List<HelloAction.GreetingInput> inputs2 = new List<HelloAction.GreetingInput>{ input2 };
List<HelloAction.GreetingOutput> outputs2 = HelloAction.getGreeting(inputs2);

System.debug('=== NO-NAME RESULT ===');
System.debug(outputs2[0].greetingMessage);
