// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract UserAuthentication {
    // Structure to store user information
    struct User {
        bytes32 passwordHash;
        bool exists;
        string username;
    }

    // Structure for documents
    struct Document {
        string documentName;
        string photoCid;
        string jsonCid;
    }

    // Structure for phone numbers
    struct Phonenumber {
        string phonenumber;
    }

    // Mappings to store users and their details
    mapping(bytes32 => User) private users;
    mapping(bytes32 => Document[]) private userDocuments;
    mapping(bytes32 => Phonenumber[]) private userPhonenumbers;
    mapping(bytes32 => mapping(bytes32 => bool)) private doctorAccess;

    // Array to store all registered username hashes
    bytes32[] private usernameHashes;

    // Events
    event UserRegistered(bytes32 indexed usernameHash);
    event LoginAttempt(bytes32 indexed usernameHash, bool success);
    event DocumentUploaded(bytes32 indexed usernameHash, string documentName);
    event PhoneUploaded(bytes32 indexed usernameHash, string phonenumber);

    // Function to register a new user
    function registerUser(string memory username, string memory password) public returns (bool) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        require(!users[usernameHash].exists, "Username already taken");

        bytes32 passwordHash = keccak256(abi.encodePacked(password));
        users[usernameHash] = User(passwordHash, true, username);

        usernameHashes.push(usernameHash);
        emit UserRegistered(usernameHash);

        return true;
    }

    // Function for user login
    function login(string memory username, string memory password) public returns (bool) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        bytes32 passwordHash = keccak256(abi.encodePacked(password));

        bool success = users[usernameHash].exists && users[usernameHash].passwordHash == passwordHash;
        emit LoginAttempt(usernameHash, success);

        return success;
    }

    // Add a document for a user
    function addDocument(
        string memory username,
        string memory documentName,
        string memory photoCid,
        string memory jsonCid
    ) public returns (bool) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        require(users[usernameHash].exists, "User does not exist");

        Document memory newDocument = Document(documentName, photoCid, jsonCid);
        userDocuments[usernameHash].push(newDocument);
        emit DocumentUploaded(usernameHash, documentName);

        return true;
    }

    // Add a phone number for a user
    function addPhoneNumber(string memory username, string memory phonenumber) public returns (bool) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        require(users[usernameHash].exists, "User does not exist");

        Phonenumber memory newPhonenumber = Phonenumber(phonenumber);
        userPhonenumbers[usernameHash].push(newPhonenumber);
        emit PhoneUploaded(usernameHash, phonenumber);

        return true;
    }

    // Get all phone numbers for a user
    function getPhoneNumbers(string memory username) public view returns (string[] memory) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        require(users[usernameHash].exists, "User does not exist");

        uint256 phoneCount = userPhonenumbers[usernameHash].length;
        string[] memory phoneNumbers = new string[](phoneCount);

        for (uint256 i = 0; i < phoneCount; i++) {
            phoneNumbers[i] = userPhonenumbers[usernameHash][i].phonenumber;
        }

        return phoneNumbers;
    }

    // Get all documents for a user
    function getDocuments(string memory username) public view returns (Document[] memory) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        require(users[usernameHash].exists, "User does not exist");

        return userDocuments[usernameHash];
    }

    // Toggle doctor access for a patient
    function toggleDoctorAccess(
        string memory patientId,
        string memory doctorId,
        bool hasAccess
    ) public {
        bytes32 patientHash = keccak256(abi.encodePacked(patientId));
        bytes32 doctorHash = keccak256(abi.encodePacked(doctorId));
        doctorAccess[patientHash][doctorHash] = hasAccess;
    }

    // Function to get all registered users
    function getRegisteredUsers() public view returns (bytes32[] memory) {
        return usernameHashes;
    }

    // Check doctor access for a patient
    function checkAccess(
        string memory patientId,
        string memory doctorId
    ) public view returns (bool) {
        bytes32 patientHash = keccak256(abi.encodePacked(patientId));
        bytes32 doctorHash = keccak256(abi.encodePacked(doctorId));

        return doctorAccess[patientHash][doctorHash];
    }

    // Add a userExists function to check if a user exists
    function userExists(string memory username) public view returns (bool) {
        bytes32 usernameHash = keccak256(abi.encodePacked(username));
        return users[usernameHash].exists;
    }
}
